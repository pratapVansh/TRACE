from pydantic import BaseModel, Field


class ComponentHealth(BaseModel):
    """State of one dependency.

    ``checked`` distinguishes a live reading from a startup snapshot, because
    the two are not equally trustworthy and collapsing them would overstate
    what this endpoint knows. Components marked ``startup`` were probed once
    during boot and may have failed since; the dedicated endpoints
    (``/api/vector/health``, ``/api/graph/health``, ``/api/llm/health``) probe
    them live.
    """

    status: str = Field(description="ok | degraded | unavailable | off")
    checked: str = Field(description="live | startup")
    required: bool = Field(
        description="Whether the service can serve its core purpose without it.",
    )
    detail: str | None = Field(
        default=None,
        description="What is wrong and what it costs, when not ok.",
    )


class HealthResponse(BaseModel):
    status: str = Field(
        description=(
            "ok = everything up. degraded = serving, but at least one component "
            "is down or impaired. unavailable = a required component is down."
        ),
    )
    service: str
    # Named explicitly so a caller does not have to walk `components` to find
    # out whether anything is wrong.
    degraded: list[str] = Field(
        default_factory=list,
        description="Components that are not ok.",
    )
    components: dict[str, ComponentHealth] = Field(default_factory=dict)
