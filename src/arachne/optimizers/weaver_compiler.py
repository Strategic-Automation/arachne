"""Standalone BootstrapFewShot compiler for all GraphWeaver sub-predictors.

This is a **build-time tool**, not application code. It uses DSPy's native
``save()`` to persist compiled predictors. At runtime, GraphWeaver uses
``load()`` to restore them — zero custom serialization.

Compiles three sub-predictors:
    1. ``weave``     — GraphWeaverSignature (topology generation)
    2. ``selector``  — CategorySelectorSignature (skill category selection)
    3. ``clarifier`` — GoalClarifierSignature (goal completeness analysis)

Usage:
    # CLI (recommended)
    uv run arachne compile-weaver

    # Python API
    python -m arachne.optimizers.weaver_compiler \\
        --teacher-model "openrouter/qwen/qwen3.6-plus:free" \\
        --output-dir ~/.local/share/arachne
"""

import contextlib
import logging
from pathlib import Path

import dspy

logger = logging.getLogger(__name__)

# Default output directory (DSPy native JSON format)
DEFAULT_OUTPUT_DIR = Path.home() / ".local" / "share" / "arachne"

# File names for each compiled predictor
WEAVE_COMPILED = "weaver_compiled.json"
SELECTOR_COMPILED = "selector_compiled.json"
CLARIFIER_COMPILED = "clarifier_compiled.json"


def _compile_predictor(
    predictor: dspy.Predict,
    trainset: list[dspy.Example],
    metric,
    max_demos: int = 4,
    teacher_lm: dspy.LM | None = None,
    max_rounds: int = 1,
) -> dspy.Predict:
    """Compile a single predictor with BootstrapFewShot."""
    from dspy.teleprompt import BootstrapFewShot

    optimizer = BootstrapFewShot(
        metric=metric,
        max_bootstrapped_demos=max_demos,
        max_labeled_demos=len(trainset),
        max_rounds=max_rounds,
    )

    compile_context = dspy.settings.context(lm=teacher_lm) if teacher_lm else contextlib.nullcontext()
    with compile_context:
        compiled = optimizer.compile(predictor, trainset=trainset)

    return compiled


def compile_weaver(
    settings=None,
    teacher_model: str | None = None,
    max_demos: int = 4,
    output_dir: Path | str | None = None,
) -> Path:
    """Compile all GraphWeaver sub-predictors with BootstrapFewShot.

    Args:
        settings: Arachne Settings (created from env if None).
        teacher_model: Optional teacher model override for bootstrapping.
        max_demos: Maximum bootstrapped demonstrations per predictor.
        output_dir: Where to save compiled predictors.

    Returns:
        Path to the output directory.
    """
    from arachne.config import Settings, configure_dspy
    from arachne.topologies.weaver import GraphWeaver

    if settings is None:
        settings = Settings.from_yaml()

    # Ensure DSPy is configured
    configure_dspy(settings)

    # Create weaver (this discovers tools and skills)
    weaver = GraphWeaver(settings=settings)

    # Teacher model: use a larger model if specified to generate bootstrapped demos
    effective_teacher = teacher_model or settings.weaver_teacher_model
    if effective_teacher:
        # Route through the configured backend (e.g. openrouter/) if not already prefixed
        if settings.llm_backend and not effective_teacher.startswith(f"{settings.llm_backend}/"):
            effective_teacher = f"{settings.llm_backend}/{effective_teacher}"
        teacher_lm = dspy.LM(
            model=effective_teacher,
            api_key=settings.llm_api_key.get_secret_value() or None,
            api_base=settings.llm_base_url or None,
        )
    else:
        teacher_lm = None

    out_dir = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    # ── 1. Compile: weave predictor (topology generation) ──────────────────
    from arachne.optimizers.weaver_demos import get_training_examples

    def weaver_metric(example: dspy.Example, pred: dspy.Prediction, trace=None) -> bool:
        topology = getattr(pred, "topology", None)
        if topology is None:
            return False
        try:
            topology.model_validate(topology.model_dump())
            return len(topology.nodes) >= 1
        except Exception:
            return False

    weave_trainset = get_training_examples()
    logger.info(
        "Compiling weave predictor: %d training examples, teacher=%s, max_demos=%d",
        len(weave_trainset),
        effective_teacher or "same-as-student",
        max_demos,
    )
    compiled_weave = _compile_predictor(weaver.weave, weave_trainset, weaver_metric, max_demos, teacher_lm)
    weave_path = out_dir / WEAVE_COMPILED
    compiled_weave.save(str(weave_path))
    logger.info("Compiled weave predictor saved to %s (%d demos)", weave_path, len(compiled_weave.demos))

    # ── 2. Compile: selector predictor (category selection) ────────────────
    from arachne.optimizers.weaver_demos import get_category_examples

    def selector_metric(example: dspy.Example, pred: dspy.Prediction, trace=None) -> bool:
        selected = getattr(pred, "selected_categories", [])
        expected = example.selected_categories
        if not selected or not expected:
            return False
        # At least one expected category must appear in selected
        return bool(set(selected) & set(expected))

    selector_trainset = get_category_examples()
    logger.info(
        "Compiling selector predictor: %d training examples, teacher=%s",
        len(selector_trainset),
        effective_teacher or "same-as-student",
    )
    compiled_selector = _compile_predictor(weaver.selector, selector_trainset, selector_metric, max_demos, teacher_lm)
    selector_path = out_dir / SELECTOR_COMPILED
    compiled_selector.save(str(selector_path))
    logger.info("Compiled selector predictor saved to %s (%d demos)", selector_path, len(compiled_selector.demos))

    # ── 3. Compile: clarifier predictor (goal completeness) ────────────────
    from arachne.optimizers.weaver_demos import get_clarifier_examples

    def clarifier_metric(example: dspy.Example, pred: dspy.Prediction, trace=None) -> bool:
        is_complete = getattr(pred, "is_complete", None)
        expected_complete = example.is_complete
        if is_complete is None:
            return False
        return is_complete == expected_complete

    clarifier_trainset = get_clarifier_examples()
    logger.info(
        "Compiling clarifier predictor: %d training examples, teacher=%s",
        len(clarifier_trainset),
        effective_teacher or "same-as-student",
    )
    compiled_clarifier = _compile_predictor(
        weaver.clarifier, clarifier_trainset, clarifier_metric, max_demos, teacher_lm
    )
    clarifier_path = out_dir / CLARIFIER_COMPILED
    compiled_clarifier.save(str(clarifier_path))
    logger.info("Compiled clarifier predictor saved to %s (%d demos)", clarifier_path, len(compiled_clarifier.demos))

    return out_dir


def has_compiled_demos(path: Path | str | None = None) -> bool:
    """Check if compiled weaver files exist."""
    p = Path(path) if path else DEFAULT_OUTPUT_DIR / WEAVE_COMPILED
    return p.exists()


def load_compiled_predictor(predictor: dspy.Predict, path: Path | str | None = None) -> int:
    """Load pre-compiled demos into a predictor using DSPy's native load().

    Returns the number of demos loaded (0 if file doesn't exist).
    """
    p = Path(path) if path else DEFAULT_OUTPUT_DIR / WEAVE_COMPILED
    if not p.exists():
        return 0

    try:
        predictor.load(path=str(p))
        demo_count = len(predictor.demos)
        logger.debug("Loaded %d compiled demos from %s", demo_count, p)
        return demo_count
    except Exception as e:
        logger.warning("Failed to load compiled demos from %s: %s", p, e)
        return 0


def load_all_compiled(weaver, output_dir: Path | str | None = None) -> dict[str, int]:
    """Load all compiled predictors into a GraphWeaver instance.

    Returns dict mapping predictor name -> demo count loaded.
    """
    base = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    results = {}

    # Weave predictor
    weave_count = load_compiled_predictor(weaver.weave, base / WEAVE_COMPILED)
    results["weave"] = weave_count

    # Selector predictor
    selector_count = load_compiled_predictor(weaver.selector, base / SELECTOR_COMPILED)
    results["selector"] = selector_count

    # Clarifier predictor
    clarifier_count = load_compiled_predictor(weaver.clarifier, base / CLARIFIER_COMPILED)
    results["clarifier"] = clarifier_count

    return results


def main() -> None:
    """CLI entry point for standalone compilation."""
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(levelname)-8s %(message)s")

    parser = argparse.ArgumentParser(description="Compile GraphWeaver with BootstrapFewShot")
    parser.add_argument(
        "--teacher-model", default=None, help="Teacher model for bootstrapping (default: uses student model)"
    )
    parser.add_argument("--max-demos", type=int, default=4, help="Max bootstrapped demos per predictor (default: 4)")
    parser.add_argument(
        "--output-dir", default=str(DEFAULT_OUTPUT_DIR), help=f"Output directory (default: {DEFAULT_OUTPUT_DIR})"
    )
    args = parser.parse_args()

    output_dir = compile_weaver(
        teacher_model=args.teacher_model,
        max_demos=args.max_demos,
        output_dir=args.output_dir,
    )
    print(f"✓ All compiled predictors saved to {output_dir}/")
    print(f"  - {WEAVE_COMPILED}")
    print(f"  - {SELECTOR_COMPILED}")
    print(f"  - {CLARIFIER_COMPILED}")


if __name__ == "__main__":
    main()
