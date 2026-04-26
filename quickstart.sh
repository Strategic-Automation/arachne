#!/usr/bin/env bash
# Arachne Quickstart -- interactive setup wizard
# Walks the user through every config decision with real model lists
set -euo pipefail

###############################################################################
# Colours
###############################################################################
RED='\033[0;31m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'
YELLOW='\033[1;33m'; MAGENTA='\033[0;35m'; WHITE='\033[1;37m'
BOLD='\033[1m'; DIM='\033[2m'; NC='\033[0m'

###############################################################################
# Helpers
###############################################################################
 banner() {
    echo -e "${CYAN}${BOLD}"
    cat <<'ASCII'
 █████  ██████   █████   ██████ ██   ██ ███    ██ ███████ 
██   ██ ██   ██ ██   ██ ██      ██   ██ ████   ██ ██      
███████ ██████  ███████ ██      ███████ ██ ██  ██ █████   
██   ██ ██   ██ ██   ██ ██      ██   ██ ██  ██ ██ ██      
██   ██ ██   ██ ██   ██  ██████ ██   ██ ██   ████ ███████ 
ASCII
    echo -e "${WHITE}${DIM}  Runtime harness for production AI agents${NC}"
    echo ""
}

divider() { echo -e "${DIM}────────────────────────────────────────────────────${NC}"; }

prompt_val() {
    local label="$1" def="${2:-}"
    local val=""
    read -rp "$(echo -e "  ${YELLOW}${BOLD}${label}${NC} ${DIM}[${def:-<required>}]${NC} ")" val || true
    echo "${val:-$def}"
}

ask_yes() {
    local answer
    read -rp "$(echo -e "  ${YELLOW}${BOLD}$1${NC} ${DIM}[y/N]${NC} ")" answer || true
    [[ "${answer,,}" == y* ]]
}

select_num() {
    local title="$1"; shift
    local -a opts=("$@")
    local idx=0
    echo -e "\n  ${WHITE}${BOLD}${title}${NC}" >&2
    echo "" >&2
    for o in "${opts[@]}"; do
        idx=$((idx + 1))
        echo -e "    ${GREEN}$(printf '%2d' $idx).${NC} $o" >&2
    done
    echo "" >&2
    local choice=""
    while true; do
        read -rp "  $(echo -e "${YELLOW}${BOLD}Select${NC} [1-${idx}]: ")" choice || true
        if [[ "$choice" =~ ^[0-9]+$ ]] && (( choice >= 1 && choice <= idx )); then
            echo "${opts[$choice - 1]}"
            return
        fi
        echo -e "  ${RED}  Enter a number between 1 and $idx.${NC}" >&2
    done
}

###############################################################################
# Model catalogues (curated -- current as of April 2026)
###############################################################################
OPENROUTER_FREE=(
    "google/gemma-4-31b-it:free                                 — Google Gemma 4 (MoE, Thinking)"
    "mistralai/mistral-large-2026-04:free                       — Mistral Large (2026.04 Update)"
    "qwen/qwen-3.5-72b-instruct:free                            — Qwen 3.5 72B Instruct"
    "google/gemini-2.0-flash-lite-preview:free                  — Fast, cheap, decent quality"
    "meta-llama/llama-3.3-70b-instruct:free                     — Meta Llama 3.3 70B"
    "deepseek/deepseek-r1-distill-llama-70b:free               — DeepSeek R1 Distill 70B"
)

OPENROUTER_PAID=(
    "elephant/elephant-alpha-100b                                — Elephant Alpha (100B Agentic)"
    "x-ai/grok-4.20                                              — xAI Grok 4.20 (Premium Vision/Agent)"
    "anthropic/claude-4-preview                                  — Claude 4 Preview (State-of-the-art)"
    "google/gemini-2.0-pro-exp                                  — Gemini 2.0 Pro Explorer"
    "qwen/qwen-3.5-480b-instruct                                — Qwen 3.5 480B (Flagship)"
    "openai/o3-preview                                          — OpenAI o3 Preview (Reasoning)"
)

OLLAMA_MODELS=(
    "gemma4:26b                   — Google Gemma 4 (Local MoE Flagship)"
    "qwen3.5:7b                  — Qwen 3.5, 7B params (Fast Thinking)"
    "llama3.3:70b                — Llama 3.3, 70B params (Powerhouse)"
    "deepseek-r2:14b             — DeepSeek R2 reasoning model"
    "phi4:14b                    — Phi-4, 14B params, Microsoft quality"
)

###############################################################################
# MAIN
###############################################################################
banner

# ── Step 0: Prerequisites ──────────────────────────────────────────────
step=0; max=5
step=$((step+1))
echo -e "${CYAN}${BOLD}Step $step/$max${NC}  Prerequisites"
divider

if ! command -v python3 &>/dev/null; then
    echo -e "  ${RED}✗  Python 3.11+ required but not found. Install it and re-run.${NC}"
    exit 1
fi
PYVER=$(python3 --version 2>&1 | grep -oP '\d+\.\d+' | head -1)
echo -e "  ${GREEN}✓${NC}  Python $PYVER"

if ! command -v uv &>/dev/null; then
    echo -e "  ${RED}✗  uv not found. Install first:${NC}"
    echo -e "    ${YELLOW}curl -LsSf https://astral.sh/uv/install.sh | sh${NC}"
    exit 1
fi

echo -n "  Installing dependencies with uv..."
uv sync --all-extras -q 2>/dev/null
echo -e "${GREEN} done${NC}"

PW_OK=false
echo -n "  Installing Playwright browsers..."
if python3 -m playwright install chromium &>/dev/null; then
    echo -e "${GREEN} done${NC}"
    PW_OK=true
else
    echo -e " ${YELLOW}skipped${NC}  ${DIM}(browser node won't work without it)${NC}"
fi
echo ""

# ── Step 1: LLM Backend ────────────────────────────────────────────────
step=$((step+1))
echo -e "${CYAN}${BOLD}Step $step/$max${NC}  LLM Backend"
divider
echo -e "  Arachne needs an LLM to weave and execute agent graphs."
echo "  Choose your provider (keys are stored in .env, never committed):"
echo ""

BACKEND_CHOICE=$(select_num \
    "Which LLM backend?" \
    "openrouter  Many models, one API key" \
    "openai      GPT-4o, GPT-4o-mini, o1" \
    "anthropic   Claude 3.7 Sonnet, 3.5 Sonnet" \
    "ollama      100% local, no API key needed"
)
BACKEND=$(echo "$BACKEND_CHOICE" | awk '{print $1}')

LLM_MODEL=""
LLM_BASE_URL=""
LLM_API_KEY=""

case "$BACKEND" in
    openrouter)
        echo ""
        cat_choice=$(select_num \
            "Choose a tier:" \
            "free   Rate-limited, no cost" \
            "paid   Better quality, pay-per-use"
        )
        TIER=$(echo "$cat_choice" | awk '{print $1}')

        if [[ "$TIER" == "free" ]]; then
            model_raw=$(select_num \
                "Select a free OpenRouter model:" \
                "${OPENROUTER_FREE[@]}" \
                "[Custom] Enter model name manually"
            )
        else
            model_raw=$(select_num \
                "Select a paid OpenRouter model:" \
                "${OPENROUTER_PAID[@]}" \
                "[Custom] Enter model name manually"
            )
        fi

        if [[ "$model_raw" == "[Custom]"* ]]; then
            LLM_MODEL=$(prompt_val "Enter OpenRouter Model ID (e.g. google/gemini-2.0-flash)")
        else
            LLM_MODEL=$(echo "$model_raw" | awk '{print $1}')
        fi
        LLM_BASE_URL="https://openrouter.ai/api/v1/"
        LLM_API_KEY=$(prompt_val "OpenRouter API Key (sk-or-v1-...)")
        ;;
    openai)
        model_raw=$(select_num \
            "Select an OpenAI model:" \
            "gpt-4o              Best quality, ~$2.50/mtok" \
            "gpt-4o-mini         Fast, ~$0.15/mtok" \
            "o1                  Reasoning-heavy tasks"
        )
        LLM_MODEL=$(echo "$model_raw" | awk '{print $1}')
        LLM_BASE_URL="https://api.openai.com/v1/"
        LLM_API_KEY=$(prompt_val "OpenAI API Key (sk-...)")
        ;;
    anthropic)
        model_raw=$(select_num \
            "Select an Anthropic model:" \
            "claude-3.7-sonnet        Latest, best reasoning" \
            "claude-3.5-sonnet        Proven, fast"
        )
        LLM_MODEL=$(echo "$model_raw" | awk '{print $1}')
        LLM_BASE_URL="https://api.anthropic.com/v1/"
        LLM_API_KEY=$(prompt_val "Anthropic API Key (sk-ant-...)")
        ;;
    ollama)
        echo -n "  Checking for local Ollama models..."
        LOCAL_OLLAMA_RAW=$(ollama list 2>/dev/null | tail -n +2 | awk '{print $1}' || true)
        
        # Prepare selection list
        OLLAMA_OPTS=()
        if [[ -n "$LOCAL_OLLAMA_RAW" ]]; then
            echo -e "${GREEN} found $(echo "$LOCAL_OLLAMA_RAW" | wc -l)${NC}"
            while read -r m; do
                [[ -n "$m" ]] && OLLAMA_OPTS+=("$m (local)")
            done <<< "$LOCAL_OLLAMA_RAW"
        else
            echo -e "${YELLOW} none found${NC}"
        fi

        # Add curated defaults if not already in local list
        for m_curated in "${OLLAMA_MODELS[@]}"; do
            m_name=$(echo "$m_curated" | awk '{print $1}')
            found_local=false
            for m_local in "${OLLAMA_OPTS[@]}"; do
                if [[ "$m_local" == "$m_name"* ]]; then
                    found_local=true; break
                fi
            done
            if [[ "$found_local" == "false" ]]; then
                OLLAMA_OPTS+=("$m_curated")
            fi
        done
        OLLAMA_OPTS+=("[Custom] Enter model name manually")

        model_raw=$(select_num \
            "Select an Ollama model:" \
            "${OLLAMA_OPTS[@]}"
        )
        
        if [[ "$model_raw" == "[Custom]"* ]]; then
            LLM_MODEL=$(prompt_val "Enter Ollama Model Name (e.g. llama3:8b)")
        else
            LLM_MODEL=$(echo "$model_raw" | awk '{print $1}')
        fi
        LLM_BASE_URL="http://localhost:11434"
        LLM_API_KEY=""
        echo -e "  ${DIM}  No API key needed. Make sure Ollama is running:${NC}"
        echo -e "  ${DIM}    ollama serve  &&  ollama pull $LLM_MODEL${NC}"
        ;;
esac

LLM_TEMP=$(prompt_val "Temperature (0.0-2.0, lower=more deterministic)" "0.7")
LLM_MAX_TOKENS=$(prompt_val "Max generation tokens" "4096")

echo ""

# ── Step 2: Cost Budgets ───────────────────────────────────────────────
step=$((step+1))
echo -e "${CYAN}${BOLD}Step $step/$max${NC}  Cost Budgets"
divider
echo "  Arachne enforces hard cost limits. Graph stops when hit."
echo ""
COST_MAX_USD=$(prompt_val "Max USD per graph execution" "10.0")
COST_MAX_TOKENS=$(prompt_val "Max tokens per graph execution" "500000")

if ask_yes "Enable hard cost stop (abort when budget exceeded)?"; then
    COST_HARD_STOP="true"
else
    COST_HARD_STOP="false"
fi
echo ""

# ── Step 3: Langfuse ───────────────────────────────────────────────────
step=$((step+1))
echo -e "${CYAN}${BOLD}Step $step/$max${NC}  Langfuse Observability"
divider
echo "  Langfuse = distributed tracing for LLM apps."
echo "  Get per-node cost, latency, error traces, and a web dashboard."
echo "  https://cloud.langfuse.com  (free tier: 50k traces/mo)"
echo ""

if ask_yes "Enable Langfuse?"; then
    LF_ENABLED="true"
    LF_PUBLIC_KEY=$(prompt_val "Langfuse Public Key (pk-lf-...)")
    LF_SECRET_KEY=$(prompt_val "Langfuse Secret Key (sk-lf-...)")
    LF_HOST=$(prompt_val "Langfuse Host" "https://cloud.langfuse.com")
else
    LF_ENABLED="false"
    LF_PUBLIC_KEY=""
    LF_SECRET_KEY=""
    LF_HOST="https://cloud.langfuse.com"
fi
echo ""

# ── Step 4: Generate .env + arachne.yaml ───────────────────────────────
step=$((step+1))
echo -e "${CYAN}${BOLD}Step $step/$max${NC}  Configuration Files"
divider
echo "  Generating configuration..."
echo ""
echo -e "  ${WHITE}.env${NC}          ${DIM}— environment vars + secrets (git ignored)${NC}"
echo -e "  ${WHITE}arachne.yaml${NC}  ${DIM}— structured, versioned, secrets redacted${NC}"
echo ""

# -- .env (secrets here, overrides via env var) --
cat > .env <<ENVEOF
# =====================================================
# Arachne -- Environment Configuration
# Generated: $(date)
# =====================================================

# -- LLM Provider --
LLM_BACKEND=$BACKEND
LLM_MODEL=$LLM_MODEL
LLM_BASE_URL=$LLM_BASE_URL
LLM_TEMPERATURE=$LLM_TEMP
LLM_MAX_TOKENS=$LLM_MAX_TOKENS
$( [[ -n "$LLM_API_KEY" ]] && echo "LLM_API_KEY=$LLM_API_KEY" || echo "# LLM_API_KEY=<set via environment or prompt below>" )

# -- Langfuse --
LANGFUSE_ENABLED=$LF_ENABLED
LANGFUSE_PUBLIC_KEY=$LF_PUBLIC_KEY
LANGFUSE_SECRET_KEY=$LF_SECRET_KEY
LANGFUSE_HOST=$LF_HOST

# -- Cost Enforcement --
ARACHNE_COST_DEFAULT_MAX_USD=$COST_MAX_USD
ARACHNE_COST_DEFAULT_MAX_TOKENS=$COST_MAX_TOKENS
ARACHNE_COST_HARD_STOP_ENABLED=$COST_HARD_STOP

# -- Session & Skill Directories --
ARACHNE_SESSION_DIRECTORY=$HOME/.local/share/arachne/sessions
ARACHNE_SKILL_DIRECTORY=$HOME/.local/share/arachne/skills
ENVEOF

# -- arachne.yaml (structured, versioned, secrets omitted) --
cat > arachne.yaml <<YAMLEOF
# =====================================================
# Arachne -- Structured Configuration
# Generated: $(date)
#
# Edit this file for persistent, versioned configuration.
# Secrets (llm_api_key, langfuse secret_key) live in .env
# or environment variables and are loaded automatically.
# =====================================================

llm_backend: $BACKEND
llm_model: $LLM_MODEL
llm_base_url: $LLM_BASE_URL
llm_temperature: $LLM_TEMP
llm_max_tokens: $LLM_MAX_TOKENS
# llm_api_key: [set via .env or environment variable]

langfuse:
  enabled: $LF_ENABLED
  public_key: $LF_PUBLIC_KEY
  host: $LF_HOST
  sample_rate: 1.0

cost:
  default_max_usd: $COST_MAX_USD
  default_max_tokens: $COST_MAX_TOKENS
  hard_stop_enabled: $COST_HARD_STOP

session:
  directory: $HOME/.local/share/arachne/sessions

skill:
  directory: $HOME/.local/share/arachne/skills
YAMLEOF

echo "  .env lines: $(wc -l < .env)"
echo "  arachne.yaml lines: $(wc -l < arachne.yaml)"
echo ""

# ── Step 5: Add to .gitignore ──────────────────────────────────────────
step=$((step+1))
echo -e "${CYAN}${BOLD}Step $step/$max${NC}  Git Safety"
divider

if [[ -f .gitignore ]]; then
    if ! grep -q "^\.env$" .gitignore; then
        echo -e "\n# Arachne secrets\n.env" >> .gitignore
        echo -e "  ${GREEN}✓${NC}  Added .env to .gitignore"
    else
        echo -e "  ${GREEN}✓${NC}  .env already in .gitignore"
    fi
    if ! grep -q "^arachne.yaml$" .gitignore; then
        echo "arachne.yaml" >> .gitignore
        echo -e "  ${GREEN}✓${NC}  Added arachne.yaml to .gitignore"
    else
        echo -e "  ${GREEN}✓${NC}  arachne.yaml already in .gitignore"
    fi
else
    echo -e "
# Arachne secrets
.env
" > .gitignore
    echo -e "  ${GREEN}✓${NC}  Created .gitignore with .env"
fi
echo ""

# ── Done ───────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}═══════════════════════════════════════════"
echo -e "  Setup Complete!"
echo -e "═══════════════════════════════════════════${NC}"
echo ""
echo "  Configuration summary:"
echo "  ─────────────────────────────────────────────"
echo -e "  ${WHITE}LLM Backend${NC}         $BACKEND ($LLM_MODEL)"
echo -e "  ${WHITE}Temperature${NC}         $LLM_TEMP / Max tokens $LLM_MAX_TOKENS"
echo -e "  ${WHITE}Cost Budget${NC}         \$${COST_MAX_USD} / ${COST_MAX_TOKENS} tokens (hard stop: $COST_HARD_STOP)"
echo -e "  ${WHITE}Langfuse${NC}            $([ "$LF_ENABLED" = "true" ] && echo "enabled ($LF_HOST)" || echo "disabled")"
echo "  ─────────────────────────────────────────────"
echo ""
echo -e "${CYAN}${BOLD}Quick reference:${NC}"
echo ""
echo -e "  ${YELLOW}Run a goal:${NC}"
if [[ "$BACKEND" == "ollama" ]]; then
    echo -e "    ${WHITE}ollama serve && ollama pull $LLM_MODEL   # start Ollama first${NC}"
fi

echo -e "  ${YELLOW}Python API:${NC}"
echo ""
echo -e "    ${WHITE}import asyncio${NC}"
echo -e "    ${WHITE}import dspy${NC}"
echo -e "    ${WHITE}from arachne.core import Arachne${NC}"
echo -e "    ${WHITE}from arachne.config import Settings${NC}"
echo ""
echo -e "    ${WHITE}async def main():${NC}"
echo -e "    ${WHITE}    settings = Settings()  # loads .env + arachne.yaml automatically${NC}"
echo -e "    ${WHITE}    arachne = Arachne(settings, max_retries=3)${NC}"
echo -e "    ${WHITE}    async_arachne = dspy.asyncify(arachne)${NC}"
echo -e "    ${WHITE}    result = await async_arachne(goal=\"Your goal here\")${NC}"
echo -e "    ${WHITE}    for nr in result.run_result.node_results:${NC}"
echo -e "    ${WHITE}        print(f\"[{nr.status}] {nr.node_id} -> {nr.duration_seconds:.1f}s\")${NC}"
echo ""
echo -e "    ${WHITE}asyncio.run(main())${NC}"
echo ""
echo -e "${DIM}  Config files you can edit anytime:${NC}"
echo -e "${DIM}    .env              secrets and overrides${NC}"
echo -e "${DIM}    arachne.yaml      structured, versioned settings${NC}"
