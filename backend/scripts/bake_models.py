"""Download the sentence-transformers models into the image at build time.

Both models are referenced by name (``all-MiniLM-L6-v2`` and
``cross-encoder/ms-marco-MiniLM-L-6-v2``), which means sentence-transformers
resolves them through the Hugging Face hub and caches the weights under
``HF_HOME``. Without a baked cache that fetch happens on first use, so:

  * the first request after every container start stalls 30-60s while ~200MB
    of weights download, and
  * the container needs outbound access to huggingface.co to work at all,
    which is not true of CI runners or air-gapped hosts.

This script is run twice by the Dockerfile. The first run populates the cache.
The second runs with ``HF_HUB_OFFLINE=1`` set, which proves the cache is
complete: if anything still needs the network the build fails here rather than
in production.

Model names are read from the environment so the Dockerfile can pass them as
build args. The defaults must track ``embedding_model_name`` and
``rerank_model_name`` in ``app/core/config.py``.
"""

from __future__ import annotations

import os
import sys

EMBEDDING_MODEL_NAME = os.environ.get("EMBEDDING_MODEL_NAME", "all-MiniLM-L6-v2")
RERANK_MODEL_NAME = os.environ.get(
    "RERANK_MODEL_NAME", "cross-encoder/ms-marco-MiniLM-L-6-v2"
)

# all-MiniLM-L6-v2's output width. Asserted rather than assumed because a
# silently wrong model would only surface as bad retrieval much later, and
# the Qdrant collection is created with this dimensionality.
EXPECTED_EMBEDDING_DIM = 384


def main() -> int:
    offline = os.environ.get("HF_HUB_OFFLINE") == "1"
    mode = "offline verification" if offline else "download"
    print(f"[bake_models] {mode} — HF_HOME={os.environ.get('HF_HOME')!r}")

    from sentence_transformers import CrossEncoder, SentenceTransformer

    print(f"[bake_models] embedding model: {EMBEDDING_MODEL_NAME}")
    embedder = SentenceTransformer(EMBEDDING_MODEL_NAME)

    # Encode once. Instantiating the model does not necessarily touch every
    # file it needs at inference time, so a real call is what proves the
    # cache is actually complete.
    vector = embedder.encode(["containerization smoke test"])[0]
    if len(vector) != EXPECTED_EMBEDDING_DIM:
        print(
            f"[bake_models] FAIL: {EMBEDDING_MODEL_NAME} produced "
            f"{len(vector)} dimensions, expected {EXPECTED_EMBEDDING_DIM}",
            file=sys.stderr,
        )
        return 1
    print(f"[bake_models]   ok — {len(vector)} dimensions")

    print(f"[bake_models] reranker model: {RERANK_MODEL_NAME}")
    reranker = CrossEncoder(RERANK_MODEL_NAME)
    scores = reranker.predict([("what is a pump seal", "Pump P-101 seal failed.")])
    print(f"[bake_models]   ok — scored {len(scores)} pair(s)")

    if offline:
        print("[bake_models] both models load with no network access")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
