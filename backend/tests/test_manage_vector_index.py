"""Tests for the guarded vector-index migration command."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import settings
from app.services.vector_store import (
    EMBEDDING_MODEL_METADATA_KEY,
    VECTOR_DIMENSION,
    VECTOR_DIMENSION_METADATA_KEY,
)
from scripts.manage_vector_index import build_parser, stamp_existing


def test_reindex_requires_explicit_collection_confirmation():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["reindex"])


@pytest.mark.asyncio
async def test_stamp_existing_does_not_modify_vectors():
    store = MagicMock()
    store.connect = AsyncMock()
    store.collection_exists = AsyncMock(return_value=True)
    store.get_embedding_metadata = AsyncMock(return_value=({}, VECTOR_DIMENSION))
    store.stamp_embedding_metadata = AsyncMock()
    store.verify_embedding_compatibility = AsyncMock()

    await stamp_existing(store, settings.embedding_model_name)

    store.stamp_embedding_metadata.assert_awaited_once()
    store.verify_embedding_compatibility.assert_awaited_once()
    assert not hasattr(store, "delete_collection") or not store.delete_collection.called


@pytest.mark.asyncio
async def test_stamp_existing_rejects_conflicting_model_metadata():
    store = MagicMock()
    store.connect = AsyncMock()
    store.collection_exists = AsyncMock(return_value=True)
    store.get_embedding_metadata = AsyncMock(
        return_value=(
            {
                EMBEDDING_MODEL_METADATA_KEY: "other-model",
                VECTOR_DIMENSION_METADATA_KEY: VECTOR_DIMENSION,
            },
            VECTOR_DIMENSION,
        )
    )

    with pytest.raises(SystemExit, match="already declares model"):
        await stamp_existing(store, settings.embedding_model_name)


@pytest.mark.asyncio
async def test_stamp_existing_rejects_physical_dimension_mismatch():
    store = MagicMock()
    store.connect = AsyncMock()
    store.collection_exists = AsyncMock(return_value=True)
    store.get_embedding_metadata = AsyncMock(return_value=({}, VECTOR_DIMENSION * 2))

    with pytest.raises(SystemExit, match="Physical dimension"):
        await stamp_existing(store, settings.embedding_model_name)
