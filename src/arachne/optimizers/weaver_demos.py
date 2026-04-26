"""Curated training examples for BootstrapFewShot compilation of GraphWeaver.

Each example maps a goal to a valid GraphTopology, giving small models concrete
demonstrations of the expected output format. These are intentionally simple,
canonical patterns that cover the most common graph structures.
"""

from __future__ import annotations

import dspy

# Canonical demo topologies as raw dicts — validated at import time.
_SIMPLE_RESEARCH = {
    "name": "simple-research",
    "objective": "Research a factual question and synthesize an answer",
    "nodes": [
        {
            "id": "search",
            "name": "Search",
            "description": "Search the web for information about the topic",
            "role": "react",
            "inputs": ["goal"],
            "output": "search_results",
            "skills": [],
            "tools": [{"name": "duckduckgo_search_async"}],
        },
        {
            "id": "synthesize",
            "name": "Synthesize Answer",
            "description": "Combine search results into a clear, factual answer",
            "role": "predict",
            "inputs": ["search_results"],
            "output": "answer",
            "skills": [],
            "tools": [],
        },
    ],
    "edges": [{"source": "search", "target": "synthesize"}],
    "runtime_inputs": [],
    "custom_tools": [],
    "custom_skills": [],
}

_PARALLEL_RESEARCH = {
    "name": "parallel-research",
    "objective": "Research from multiple sources in parallel, then aggregate",
    "nodes": [
        {
            "id": "search_web",
            "name": "Web Search",
            "description": "Search the web for information",
            "role": "react",
            "inputs": ["goal"],
            "output": "web_results",
            "skills": [],
            "tools": [{"name": "duckduckgo_search_async"}],
        },
        {
            "id": "search_wiki",
            "name": "Wikipedia Search",
            "description": "Search Wikipedia for factual background",
            "role": "react",
            "inputs": ["goal"],
            "output": "wiki_results",
            "skills": [],
            "tools": [{"name": "wikipedia_search_async"}],
        },
        {
            "id": "aggregate",
            "name": "Aggregate Findings",
            "description": "Combine and reconcile findings from all sources",
            "role": "predict",
            "inputs": ["web_results", "wiki_results"],
            "output": "aggregated_answer",
            "skills": [],
            "tools": [],
        },
    ],
    "edges": [
        {"source": "search_web", "target": "aggregate"},
        {"source": "search_wiki", "target": "aggregate"},
    ],
    "runtime_inputs": [],
    "custom_tools": [],
    "custom_skills": [],
}

_QA_SIMPLE = {
    "name": "simple-qa",
    "objective": "Answer a straightforward factual question",
    "nodes": [
        {
            "id": "answer",
            "name": "Answer Question",
            "description": "Provide a direct answer to the user's question",
            "role": "predict",
            "inputs": ["goal"],
            "output": "answer",
            "skills": [],
            "tools": [],
        },
    ],
    "edges": [],
    "runtime_inputs": [],
    "custom_tools": [],
    "custom_skills": [],
}

_RESEARCH_AND_REPORT = {
    "name": "research-report",
    "objective": "Research a topic and produce a structured report",
    "nodes": [
        {
            "id": "search",
            "name": "Search",
            "description": "Search for information on the topic",
            "role": "react",
            "inputs": ["goal"],
            "output": "research_data",
            "skills": [],
            "tools": [{"name": "duckduckgo_search_async"}, {"name": "jina_search_async"}],
        },
        {
            "id": "analyze",
            "name": "Analyze",
            "description": "Analyze and structure the research data",
            "role": "predict",
            "inputs": ["research_data"],
            "output": "analysis",
            "skills": [],
            "tools": [],
        },
        {
            "id": "report",
            "name": "Write Report",
            "description": "Compose a final report from the analysis",
            "role": "predict",
            "inputs": ["analysis"],
            "output": "report",
            "skills": [],
            "tools": [{"name": "write_file"}],
        },
    ],
    "edges": [
        {"source": "search", "target": "analyze"},
        {"source": "analyze", "target": "report"},
    ],
    "runtime_inputs": [],
    "custom_tools": [],
    "custom_skills": [],
}

# Goal -> topology pairs for training
_DEMO_PAIRS: list[tuple[str, dict]] = [
    ("What is the capital of France?", _QA_SIMPLE),
    ("Explain the difference between TCP and UDP", _QA_SIMPLE),
    ("Research recent breakthroughs in quantum computing", _SIMPLE_RESEARCH),
    ("Find and compare the top 3 CRM software options for small business", _PARALLEL_RESEARCH),
    ("Research the history of the internet and write a summary report", _RESEARCH_AND_REPORT),
]


# ── Category Selector Training Examples ──────────────────────────────────────

_CATEGORY_PAIRS: list[tuple[str, list[str]]] = [
    ("Research recent breakthroughs in quantum computing", ["research"]),
    ("Find and compare the top 3 CRM software options for small business", ["research", "productivity"]),
    ("Write a Python script to automate email sorting", ["software-development", "email"]),
    ("Set up a CI/CD pipeline for my GitHub repo", ["devops", "github"]),
    ("Create a diagram showing the system architecture", ["diagramming", "software-development"]),
    ("Find the best pizza restaurants in Rome", ["research"]),
    ("Monitor my smart home temperature sensors and alert if too high", ["smart-home", "productivity"]),
    ("Write a blog post about AI safety", ["creative", "research"]),
    ("Deploy a machine learning model to production", ["mlops", "devops"]),
    ("Summarize my Apple Notes from last week", ["apple", "note-taking", "productivity"]),
    ("Red team this API endpoint for security vulnerabilities", ["red-teaming", "software-development"]),
    ("Search social media for mentions of our brand", ["social-media", "research"]),
    ("Generate a meme GIF for our team chat", ["gifs", "creative"]),
    ("Set up an RSS feed aggregator for AI news", ["feeds", "research"]),
    ("Scrape product data from competitor websites", ["research", "software-development"]),
]

# All known skill categories (must match folder names under skills/default/)
_ALL_CATEGORIES = sorted(
    {
        "apple",
        "autonomous-ai-agents",
        "creative",
        "data-science",
        "devops",
        "diagramming",
        "dogfood",
        "domain",
        "email",
        "feeds",
        "gaming",
        "gifs",
        "github",
        "inference-sh",
        "mcp",
        "media",
        "mlops",
        "note-taking",
        "productivity",
        "red-teaming",
        "research",
        "smart-home",
        "social-media",
        "software-development",
    }
)


# ── Goal Clarifier Training Examples ─────────────────────────────────────────

_CLARIFIER_PAIRS: list[tuple[str, bool, list[str], str]] = [
    # (goal, is_complete, clarifying_questions, reasoning)
    (
        "Research the directors of Google company and find their LinkedIn profiles",
        True,
        [],
        "Goal specifies WHAT (directors of Google), DEPTH (LinkedIn profiles), and SCOPE (specific company).",
    ),
    (
        "What is the capital of France?",
        True,
        [],
        "Straightforward factual question with no ambiguity.",
    ),
    (
        "Research something",
        False,
        ["What specific topic or subject would you like me to research?"],
        "Goal is completely vague — no topic, depth, or scope specified.",
    ),
    (
        "Write a script",
        False,
        [
            "What should the script do?",
            "What programming language should it use?",
            "Where should it run (local, server, cloud)?",
        ],
        "Goal is missing WHAT (purpose of script), and has no technical requirements.",
    ),
    (
        "Find information about a company",
        False,
        ["Which company would you like me to research?"],
        "Goal is missing a specific company name — no identifier provided.",
    ),
    (
        "Monitor the temperature sensors in my living room and send me an alert if it exceeds 30°C",
        True,
        [],
        "Goal specifies WHAT (temperature monitoring), DEPTH (alert on threshold), and SCOPE (living room sensors).",
    ),
    (
        "Help me with my emails",
        False,
        [
            "What would you like to do with your emails? (e.g., sort, search, draft, summarize)",
            "Which email account or provider?",
        ],
        "Goal is vague — 'help with emails' could mean many things.",
    ),
    (
        "Compare the top 5 project management tools and create a summary report",
        True,
        [],
        "Goal specifies WHAT (compare PM tools), DEPTH (top 5, summary report), and implied SCOPE (web research).",
    ),
]


# ── Training Example Builders ────────────────────────────────────────────────


def get_training_examples() -> list[dspy.Example]:
    """Return curated training examples for BootstrapFewShot compilation."""
    from arachne.topologies.schema import GraphTopology

    examples = []
    for goal, topo_dict in _DEMO_PAIRS:
        # Validate the topology is well-formed
        topology = GraphTopology.model_validate(topo_dict)
        examples.append(
            dspy.Example(
                goal=goal,
                available_tools="duckduckgo_search_async, wikipedia_search_async, jina_search_async, write_file",
                skill_catalog="",
                constraints_text="",
                success_criteria="Provide accurate, well-sourced information",
                available_roles="predict, react, human_in_loop, router, aggregator",
                max_nodes=10,
                modifications="",
                previous_topology="",
                failure_context="",
                topology=topology,
            ).with_inputs(
                "goal",
                "available_tools",
                "skill_catalog",
                "constraints_text",
                "success_criteria",
                "available_roles",
                "max_nodes",
                "modifications",
                "previous_topology",
                "failure_context",
            )
        )
    return examples


def get_category_examples() -> list[dspy.Example]:
    """Return curated training examples for CategorySelector compilation."""
    examples = []
    for goal, expected_cats in _CATEGORY_PAIRS:
        examples.append(
            dspy.Example(
                goal=goal,
                available_categories=", ".join(_ALL_CATEGORIES),
                selected_categories=expected_cats,
            ).with_inputs("goal", "available_categories")
        )
    return examples


def get_clarifier_examples() -> list[dspy.Example]:
    """Return curated training examples for GoalClarifier compilation."""
    examples = []
    for goal, is_complete, questions, reasoning in _CLARIFIER_PAIRS:
        examples.append(
            dspy.Example(
                goal=goal,
                is_complete=is_complete,
                clarifying_questions=questions,
                reasoning=reasoning,
            ).with_inputs("goal")
        )
    return examples
