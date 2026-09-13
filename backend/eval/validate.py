"""Validate the golden set against the frozen manifest and the indexed corpus.

    python -m eval.validate                       # schema + manifest + Postgres corpus
    python -m eval.validate --collection eval_chunks_512   # evidence coverage in a Qdrant collection
    python -m eval.validate --offline             # schema + manifest files only, no database

Errors mean the golden set cannot be trusted for scoring; warnings are
matching hazards worth knowing about. Exit status is 1 on any error.
"""

import argparse
import asyncio
import hashlib
import sys
from collections import Counter
from dataclasses import dataclass, field

from pydantic import ValidationError

from eval.corpus import chunk_fingerprint, load_postgres_chunks, load_qdrant_chunks
from eval.schema import (
    EXPECTED_SPLIT,
    MANIFEST_PATH,
    GOLDEN_SET_PATH,
    REPO_ROOT,
    CorpusManifest,
    GoldenSet,
    load_golden_set,
    load_manifest,
)
from eval.text import contains_any, contains_evidence, is_bare_number, normalize


@dataclass
class ValidationReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def validate_structure(golden: GoldenSet, manifest: CorpusManifest) -> ValidationReport:
    """Checks that need no corpus text: review state, split, manifest membership."""
    report = ValidationReport()
    known = manifest.filenames()

    for item in golden.items:
        if item.review.status == "needs_review":
            report.errors.append(f"{item.id}: not reviewed")
        if item.review.status == "rejected":
            report.errors.append(f"{item.id}: rejected item still in the set - replace it")
        if item.review.status != "needs_review" and not (
            item.review.reviewed_by and item.review.reviewed_on
        ):
            report.errors.append(f"{item.id}: review is missing reviewed_by / reviewed_on")
        for doc in item.expected_docs:
            if doc not in known:
                report.errors.append(f"{item.id}: expected doc {doc!r} is not in the manifest")
        for fact in item.expected_facts:
            for phrase in fact.any_of:
                if not normalize(phrase):
                    report.errors.append(f"{item.id}: empty accepted phrasing in {fact.fact!r}")
                elif is_bare_number(phrase):
                    report.warnings.append(
                        f"{item.id}: bare-number phrasing {phrase!r} in {fact.fact!r}"
                    )

    split = Counter(item.type for item in golden.active_items())
    if dict(split) != EXPECTED_SPLIT:
        report.errors.append(f"type split is {dict(split)}, expected {EXPECTED_SPLIT}")
    if len(golden.items) != sum(EXPECTED_SPLIT.values()):
        report.errors.append(f"{len(golden.items)} items, expected {sum(EXPECTED_SPLIT.values())}")
    return report


def validate_manifest_files(manifest: CorpusManifest, report: ValidationReport) -> None:
    """Every source file exists in demo_dataset/ with the frozen sha256."""
    for doc in manifest.documents:
        path = REPO_ROOT / doc.source_path
        if not path.exists():
            report.errors.append(f"manifest: source file missing {doc.source_path}")
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != doc.sha256:
            report.errors.append(f"manifest: sha256 drift for {doc.source_path}")


def validate_against_corpus(
    golden: GoldenSet,
    manifest: CorpusManifest,
    chunks_by_doc: dict[str, list[str]],
    report: ValidationReport,
    *,
    check_fingerprints: bool = True,
) -> None:
    """Evidence must occur in the named document's chunks; facts in its text."""
    if check_fingerprints:
        for doc in manifest.documents:
            contents = chunks_by_doc.get(doc.filename)
            if contents is None:
                report.errors.append(f"corpus: {doc.filename} is not indexed")
                continue
            if len(contents) != doc.chunk_count:
                report.errors.append(
                    f"corpus: {doc.filename} has {len(contents)} chunks, manifest says {doc.chunk_count}"
                )
            elif chunk_fingerprint(contents) != doc.chunk_fingerprint:
                report.errors.append(f"corpus: chunk fingerprint drift for {doc.filename}")

    for item in golden.active_items():
        for evidence in item.expected_evidence:
            contents = chunks_by_doc.get(evidence.doc, [])
            if not any(contains_evidence(chunk, evidence.contains) for chunk in contents):
                report.errors.append(
                    f"{item.id}: evidence not found in {evidence.doc}: {evidence.contains!r}"
                )
        doc_text = normalize(" ".join(c for d in item.expected_docs for c in chunks_by_doc.get(d, [])))
        for fact in item.expected_facts:
            if fact.in_source and not contains_any(doc_text, fact.any_of):
                report.errors.append(
                    f"{item.id}: no accepted phrasing of {fact.fact!r} occurs in the expected documents"
                )


def run(*, offline: bool, collection: str | None) -> ValidationReport:
    report = ValidationReport()
    try:
        golden = load_golden_set(GOLDEN_SET_PATH)
        manifest = load_manifest(MANIFEST_PATH)
    except ValidationError as exc:
        report.errors.append(f"schema: {exc}")
        return report

    structural = validate_structure(golden, manifest)
    report.errors += structural.errors
    report.warnings += structural.warnings
    validate_manifest_files(manifest, report)

    if collection:
        chunks = load_qdrant_chunks(collection)
        # Re-chunked collections legitimately differ from the frozen fingerprints.
        validate_against_corpus(golden, manifest, chunks, report, check_fingerprints=False)
    elif not offline:
        chunks = asyncio.run(load_postgres_chunks())
        validate_against_corpus(golden, manifest, chunks, report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--offline", action="store_true", help="skip corpus checks (no database)")
    parser.add_argument("--collection", help="check evidence against a Qdrant collection instead")
    args = parser.parse_args(argv)

    report = run(offline=args.offline, collection=args.collection)
    for warning in report.warnings:
        print(f"WARNING {warning}")
    for error in report.errors:
        print(f"ERROR   {error}")
    print(f"\n{len(report.errors)} error(s), {len(report.warnings)} warning(s)")
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
