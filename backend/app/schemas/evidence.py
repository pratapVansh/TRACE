"""Evidence-classification models.

Kept in ``schemas`` rather than beside the classifier in ``services`` because
``ChatResponse`` carries ``ClassifiedStatement`` and ``app/schemas`` is a leaf
layer — it never imports from ``app/services``.
"""

from typing import Literal

from pydantic import BaseModel, Field

Classification = Literal["FACT", "HYPOTHESIS", "UNKNOWN"]


class ClassifiedStatement(BaseModel):
    """One sentence of an answer, classified against the retrieved evidence.

    - ``FACT`` — asserted plainly and supported by a retrieved passage.
    - ``HYPOTHESIS`` — hedged by the model ("may", "likely", "suggests"),
      whether or not a passage supports it. Hedged language is never
      promoted to FACT: the model is signalling that it is inferring.
    - ``UNKNOWN`` — no retrieved passage supports it.
    """

    text: str
    classification: Classification
    # Document names of the passages supporting this statement, most
    # similar first. Empty for HYPOTHESIS/UNKNOWN with no support.
    evidence_refs: list[str] = Field(default_factory=list)


class EvidenceSummary(BaseModel):
    """Counts of each classification across a whole answer."""

    fact_count: int = 0
    hypothesis_count: int = 0
    unknown_count: int = 0

    @property
    def total(self) -> int:
        return self.fact_count + self.hypothesis_count + self.unknown_count


__all__ = ["Classification", "ClassifiedStatement", "EvidenceSummary"]
