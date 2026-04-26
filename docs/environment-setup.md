# Environment Setup

This guide covers setting up your local environment for Arachne development and execution.

## Prerequisites

- [uv](https://github.com/astral-sh/uv) (Package manager)
- Python 3.11 or newer
- [Ollama](https://ollama.com/) (For local LLMs) or API keys for [OpenAI/Anthropic/Groq]

## Installation

```bash
git clone https://github.com/Strategic-Automation/arachne.git
cd arachne
uv sync
```

## Initial Configuration

Copy the example environment file:
```bash
cp .env.example .env
```
Edit `.env` to include your provider settings.
