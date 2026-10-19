"""Checker registry.

A checker is an object with a ``kind`` string and ``check(ctx) -> Outcome``.
Built-in kinds are registered at import time; optional modules (statistics,
lean4, external) are discovered lazily so the core stays importable even before
those modules are installed or authored.
"""

from __future__ import annotations

import importlib
from typing import Any

from .base import CheckContext, Outcome, RunResult, Runner, run_command, sha256_text, truncate

REGISTRY: dict[str, Any] = {}


def register(kind: str, checker: Any) -> None:
    if not kind:
        raise ValueError("checker kind must be a non-empty string")
    REGISTRY[kind] = checker


def get_checker(kind: str) -> Any | None:
    return REGISTRY.get(kind)


def _bootstrap() -> None:
    from .executables import ExitChecker, NumericChecker, StdoutChecker
    from .human import HumanChecker

    for checker in (NumericChecker(), StdoutChecker(), ExitChecker(), HumanChecker()):
        register(checker.kind, checker)

    optional = (
        ("statistics", "StatisticsChecker"),
        ("lean4", "Lean4Checker"),
        ("external", "ExternalChecker"),
    )
    for module_name, class_name in optional:
        try:
            module = importlib.import_module(f".{module_name}", __name__)
        except ModuleNotFoundError:
            # Optional checker not present yet; the engine reports INCONCLUSIVE
            # for that kind instead of failing the whole audit.
            continue
        checker_class = getattr(module, class_name, None)
        if checker_class is None:
            continue
        try:
            instance = checker_class()
        except Exception:  # noqa: BLE001 - a broken optional checker must not break core
            continue
        register(getattr(instance, "kind", module_name), instance)


_bootstrap()

__all__ = [
    "REGISTRY",
    "CheckContext",
    "Outcome",
    "RunResult",
    "Runner",
    "get_checker",
    "register",
    "run_command",
    "sha256_text",
    "truncate",
]
