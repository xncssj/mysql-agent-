"""Evaluation utilities for MySQL Agent."""

__all__ = ["EvalCaseResult", "load_golden_set", "run_evaluation"]


def __getattr__(name: str):
    if name in __all__:
        from .run import EvalCaseResult, load_golden_set, run_evaluation

        return {
            "EvalCaseResult": EvalCaseResult,
            "load_golden_set": load_golden_set,
            "run_evaluation": run_evaluation,
        }[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
