# Triangulated Evaluation: The Three Levels of Verification

To ensure the reliability and quality of agentic workflows, Arachne uses a multi-layered verification strategy known as "Triangulated Evaluation."

## Level 0: Rule-Based Checks (Automatic, Immediate)

These are deterministic checks against quantitative or hard constraints.

- **Example**: Ensure the total cost is under $1.00 or the response contains a specific keyword.
- **Outcome**: Binary (Pass/Fail).

## Level 1: Semantic Checks (Model-Based)

A specialized DSPy module (the `SemanticEvaluator`) reviews the output against the `GoalDefinition` and `SuccessCriteria`.

- **Example**: Does the generated holiday plan meet all the traveler's preferences?
- **Outcome**: A confidence score (0.0 to 1.0).

## Level 2: Human-in-the-Loop (HITL)

If the semantic confidence score is below a predefined threshold, the system triggers a pause.

- **Example**: The system is 60% confident that the plan is correct but needs a person to verify.
- **Outcome**: Interactive review via the CLI.
