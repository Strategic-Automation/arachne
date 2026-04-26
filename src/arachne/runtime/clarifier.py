"""Goal Clarifier -- Analyzes goals for ambiguity and missing details."""

import dspy
from pydantic import BaseModel, Field


class ClarificationResult(BaseModel):
    """Result of goal analysis."""

    is_complete: bool = Field(..., description="True if the goal is detailed enough to design a multi-agent graph.")
    clarifying_questions: list[str] = Field(
        default_factory=list,
        description="Specific questions to ask the user if is_complete is False.",
    )
    reasoning: str = Field(..., description="Brief explanation of why the goal is complete or not.")


class ClarifierSignature(dspy.Signature):
    """Analyze the user's goal for ambiguity or missing details.

    A goal is COMPLETE if it specifies:
    - WHAT: The core entity or task (e.g. 'company').
    - DEPTH: How much detail is needed (e.g. 'find directors and bios').
    - SCOPE: Where to look (e.g. 'check social media and deep web').

    A goal is UNDERSPECIFIED if it is:
    - Vague: 'Research something', 'Find info', 'Write a script'.
    - Missing Identifiers: 'Research a company' without a name.
    - Too broad: 'Tell me about AI'.

    If UNDERSPECIFIED, return is_complete=False and 1-3 targeted questions.
    If COMPLETE, return is_complete=True and an empty questions list.
    """

    goal: str = dspy.InputField()
    analysis: ClarificationResult = dspy.OutputField()


class GoalClarifier(dspy.Module):
    """DSPy module to analyze and clarify user goals."""

    def __init__(self):
        super().__init__()
        self.analyze = dspy.Predict(ClarifierSignature)

    def forward(self, goal: str) -> dspy.Prediction:
        result = self.analyze(goal=goal)
        return dspy.Prediction(
            is_complete=result.analysis.is_complete,
            questions=result.analysis.clarifying_questions,
            reasoning=result.analysis.reasoning,
        )
