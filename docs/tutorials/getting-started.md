# Getting Started with Arachne

Arachne is an agentic research and execution engine. This guide will help you set up and run your first agent in minutes.

## Prerequisites

- **Python 3.11+**
- **[uv](https://github.com/astral-sh/uv)** (Recommended for speed and reliability)

## Step 1: Clone and Setup

```bash
git clone https://github.com/Strategic-Automation/arachne.git
cd arachne
```

## Step 2: Run the Quickstart Script

The interactive setup wizard handles dependency installation, tool provisioning, and configuration.

```bash
./quickstart.sh
```

Follow the prompts to select your LLM provider. If you're new to Arachne, **Ollama** is recommended for 100% local, free execution (requires [Ollama](https://ollama.com) to be installed and running).

## Step 3: Understanding Configuration

The quickstart script generates two local files for you:

1.  **`.env`**: Stores your **secrets** (e.g., `LLM_API_KEY`). This file is git-ignored for your security.
2.  **`arachne.yaml`**: Stores your **settings** (e.g., model name, cost budgets). This is used by the Python framework and CLI by default.

## Step 4: Run Your First Agent

Once the quickstart completes, describe any goal in natural language:

```bash
# Example research goal
uv run arachne run "Research the current state of humanoid robotics in 2025"
```

### 🤝 Best Practice: Interactive Guidance

If your goal is complex or you want to ensure the agent stays on track, use the **`--interactive`** (or `-i`) flag:

```bash
uv run arachne run "Research a company" -i
```

In interactive mode, Arachne will:
1.  **Clarify**: Ask follow-up questions if your goal is too vague.
2.  **Review**: Show you the planned graph before starting.
3.  **Approve**: Pause for feedback if results seem marginal.
4.  **Final Gate**: Ask if you're happy with the output before finishing.

## How It Works

1.  **Weave**: Arachne uses an LLM to "weave" an agent graph (DAG) tailored to your goal.
2.  **Execute**: The graph runs in topological waves, executing nodes in parallel where possible.
3.  **Heal**: If a node fails or produces low-quality data, Arachne automatically diagnoses and repairs the graph.

## Next Steps

- Explore the [Architecture Deep-Dive](../explanation/architecture.md)
- Check the [CLI Reference](../reference/cli.md) for more commands
- Learn how to add [Custom Tools](../guides/developer-guide.md)