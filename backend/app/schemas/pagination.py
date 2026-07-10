import math
from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    total_items: int
    total_pages: int
    has_next: bool
    has_previous: bool


def build_pagination_metadata(
    total: int,
    skip: int,
    limit: int,
) -> dict:
    page = (skip // limit) + 1
    total_pages = max(1, math.ceil(total / limit)) if limit > 0 else 1
    return {
        "total": total,
        "page": page,
        "page_size": limit,
        "total_items": total,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_previous": page > 1,
    }
