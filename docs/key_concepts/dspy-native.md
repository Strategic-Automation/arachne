# DSPy-Native Architecture

Arachne is built on the [DSPy](https://github.com/stanfordnlp/dspy) framework, which allows for programmatic optimization of language model prompts and weights.

## What is DSPy-Native?

In Arachne, being "DSPy-native" means that every intelligent system component is implemented as a `dspy.Module`.

- **Declarative Logic**: Instead of hardcoding prompts, we define input/output signatures (`dspy.Signature`) and pass them to modules.
- **Optimization Hooks**: Components like the Weaver and Evaluator are designed to be optimized through DSPy's teleprompters.
- **Thin Orchestration**: The framework's core code is minimal, providing only the necessary scaffolding to execute DSPy modules.

---

# The Pointer Pattern: Handling Large Data

One of the most significant challenges in building autonomous agents is managing the context window of LLMs.

## Large Payloads

When a tool returns a massive amount of data (e.g., >10KB), passing it directly to the LLM can result in truncated responses or loss of focus.

## How it Works

The Pointer Pattern solves this issue by:

1. **Spillover Detection**: The framework monitors tool outputs.
2. **Disk Persistence**: Results exceeding a threshold are saved to a session-specific directory on disk.
3. **Pointers**: The LLM receives a lightweight "pointer" (a unique ID and file path) instead of the full payload.
4. **On-Demand Retrieval**: The agent can "read" specific chunks of the data using dedicated tools (e.g., `read_pointer`) only when needed.

---

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
