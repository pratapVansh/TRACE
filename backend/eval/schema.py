"""Pydantic models for the golden set and the frozen corpus manifest."""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

EVAL_DIR = Path(__file__).resolve().parent
GOLDEN_SET_PATH = EVAL_DIR / "golden_set.yaml"
MANIFEST_PATH = EVAL_DIR / "corpus_manifest.yaml"
REPO_ROOT = EVAL_DIR.parent.parent

ItemType = Literal["single_hop", "multi_hop", "follow_up", "negative"]
Tag = Literal[
    "compound",
    "table_row",
    "no_lexical_overlap",
    "entity_resolution",
    "ocr_source",
    "false_premise",
    "distractor_doc",
    "long_doc",
]
ID_PREFIX = {"single_hop": "S", "multi_hop": "M", "follow_up": "F", "negative": "N"}
EXPECTED_SPLIT = {"single_hop": 20, "multi_hop": 10, "follow_up": 5, "negative": 5}


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HistoryTurn(_Strict):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1)


class Evidence(_Strict):
    doc: str
    contains: str = Field(min_length=3)


class Fact(_Strict):
    fact: str = Field(min_length=1)
    any_of: list[str] = Field(min_length=1)
    in_source: bool = True


class Review(_Strict):
    status: Literal["approved", "revised", "rejected", "needs_review"]
    reviewed_by: str | None = None
    reviewed_on: str | None = None
    notes: str = ""


class GoldenItem(_Strict):
    id: str = Field(pattern=r"^[SMFN]\d{2}$")
    type: ItemType
    source: str
    question: str = Field(min_length=5)
    history: list[HistoryTurn] = Field(default_factory=list)
    expected_resolution: list[str] = Field(default_factory=list)
    expected_docs: list[str]
    expected_evidence: list[Evidence]
    expected_facts: list[Fact]
    must_refuse: bool
    tags: list[Tag] = Field(default_factory=list)
    review: Review

    @model_validator(mode="after")
    def _consistent_with_type(self) -> "GoldenItem":
        problems: list[str] = []
        if not self.id.startswith(ID_PREFIX[self.type]):
            problems.append(f"id prefix does not match type {self.type}")

        negative = self.type == "negative"
        if negative != self.must_refuse:
            problems.append("must_refuse must be true exactly for negative items")
        if negative and (self.expected_docs or self.expected_evidence or self.expected_facts):
            problems.append("negative items must have no expected docs, evidence or facts")
        if not negative and not (self.expected_docs and self.expected_evidence and self.expected_facts):
            problems.append("answerable items need expected docs, evidence and facts")

        follow_up = self.type == "follow_up"
        if follow_up and not (self.history and self.expected_resolution):
            problems.append("follow_up items need history and expected_resolution")
        if not follow_up and (self.history or self.expected_resolution):
            problems.append("only follow_up items may carry history or expected_resolution")
        if self.history:
            roles = [turn.role for turn in self.history]
            if roles[0] != "user" or roles[-1] != "assistant" or any(
                a == b for a, b in zip(roles, roles[1:])
            ):
                problems.append("history must alternate user/assistant, starting with user")

        if self.type == "multi_hop" and len(set(self.expected_docs)) < 2:
            problems.append("multi_hop items need at least two expected documents")
        if len(set(self.expected_docs)) != len(self.expected_docs):
            problems.append("expected_docs contains duplicates")
        for evidence in self.expected_evidence:
            if evidence.doc not in self.expected_docs:
                problems.append(f"evidence document {evidence.doc!r} is not in expected_docs")

        if problems:
            raise ValueError("; ".join(problems))
        return self


class GoldenSet(_Strict):
    golden_set_version: int
    corpus_manifest: str
    drafted_by: str
    drafted_on: str
    review_status: str
    items: list[GoldenItem]

    @model_validator(mode="after")
    def _unique_ids(self) -> "GoldenSet":
        ids = [item.id for item in self.items]
        duplicates = sorted({i for i in ids if ids.count(i) > 1})
        if duplicates:
            raise ValueError(f"duplicate item ids: {duplicates}")
        return self

    def active_items(self) -> list[GoldenItem]:
        return [item for item in self.items if item.review.status != "rejected"]


class ManifestDocument(_Strict):
    filename: str
    source_path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    doc_type: str
    extraction_method: str
    chunk_count: int = Field(ge=1)
    extracted_chars: int = Field(ge=0)
    chunk_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")


class ExcludedDocument(_Strict):
    filename: str
    sha256: str
    chunk_count: int
    reason: str


class CorpusManifest(_Strict):
    manifest_version: int
    frozen_at: str
    pipeline_at_freeze: dict
    totals: dict
    documents: list[ManifestDocument]
    excluded: list[ExcludedDocument] = Field(default_factory=list)

    def filenames(self) -> set[str]:
        return {doc.filename for doc in self.documents}

    def excluded_filenames(self) -> set[str]:
        return {doc.filename for doc in self.excluded}


def load_golden_set(path: Path = GOLDEN_SET_PATH) -> GoldenSet:
    return GoldenSet.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def load_manifest(path: Path = MANIFEST_PATH) -> CorpusManifest:
    return CorpusManifest.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
