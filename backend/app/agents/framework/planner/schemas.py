from pydantic import BaseModel, Field


class ExecutionStep(BaseModel):
    """One step in an execution plan.

    Each step may invoke an agent or perform an LLM-only operation.
    Dependencies are expressed via ``depends_on`` (previous step ids)
    so the executor can topologically sort and parallelise
    independent steps.
    """

    step_id: str
    description: str
    agent_id: str | None = None
    depends_on: list[str] = Field(default_factory=list)
    parallel_with: list[str] = Field(default_factory=list)
    retry_on_failure: bool = True
    max_retries: int = 1
    fallback_agent_id: str | None = None
    required_data: list[str] = Field(default_factory=list)
    output_key: str = ""
    llm_prompt_template: str | None = None


class ExecutionPlan(BaseModel):
    """A dynamic plan produced by the ``PlannerAgent``.

    The plan is a DAG of ``ExecutionStep`` objects.  The executor
    walks the DAG in topological order, running independent steps
    in parallel and dependent steps sequentially.  Results from
    each step are keyed by ``output_key`` and passed to subsequent
    steps via the shared context.
    """

    goal: str
    steps: list[ExecutionStep]
    reasoning: str = ""
    estimated_complexity: str = "moderate"
    requires_supervision: bool = False
