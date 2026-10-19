"""Shared types for paperunit checkers.

A checker maps one paper claim (plus its preregistered check spec) to an
:class:`Outcome`.  Checkers never compute aggregate scores or rankings; they
report evidence-local verdicts only.

The four verdicts are:

* ``SUPPORTED``    - the check ran and every preregistered expectation was met.
* ``REFUTED``      - the check ran and a preregistered expectation was violated.
* ``INCONCLUSIVE`` - the check could not decide (toolchain missing, timeout,
                     underpowered statistics, malformed formalisation, ...).
* ``NOT_RUN``      - the claim has no executable check (e.g. a human review note).
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Literal, Protocol

Verdict = Literal["SUPPORTED", "REFUTED", "INCONCLUSIVE", "NOT_RUN"]
VERDICTS: tuple[str, ...] = ("SUPPORTED", "REFUTED", "INCONCLUSIVE", "NOT_RUN")

DEFAULT_TIMEOUT_S = 120.0


def canonical_json(obj: Any) -> str:
    """Stable JSON encoding used for hashing and comparisons."""
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8", errors="replace"))


def truncate(text: str, limit: int = 4000) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n... [truncated {len(text) - limit} chars]"


@dataclass
class RunResult:
    """Result of executing one command for a checker."""

    cmd: str
    cwd: str
    timeout_s: float
    exit_code: int | None
    timed_out: bool
    duration_s: float
    stdout: str
    stderr: str

    @property
    def stdout_sha256(self) -> str:
        return sha256_text(self.stdout)

    @property
    def stderr_sha256(self) -> str:
        return sha256_text(self.stderr)

    @property
    def evidence_sha256(self) -> str:
        return sha256_text(
            canonical_json(
                {
                    "cmd": self.cmd,
                    "cwd": self.cwd,
                    "exit_code": self.exit_code,
                    "timed_out": self.timed_out,
                    "stdout_sha256": self.stdout_sha256,
                    "stderr_sha256": self.stderr_sha256,
                }
            )
        )

    def summary(self) -> dict[str, Any]:
        return {
            "cmd": self.cmd,
            "cwd": self.cwd,
            "timeout_s": self.timeout_s,
            "exit_code": self.exit_code,
            "timed_out": self.timed_out,
            "duration_s": round(self.duration_s, 4),
            "evidence_sha256": self.evidence_sha256,
            "stdout_sha256": self.stdout_sha256,
            "stderr_sha256": self.stderr_sha256,
            "stdout_excerpt": truncate(self.stdout, 2000),
            "stderr_excerpt": truncate(self.stderr, 1000),
        }


def run_command(
    cmd: str,
    cwd: Path,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    env: dict[str, str] | None = None,
) -> RunResult:
    """Execute a shell command, capturing output. Never raises on failure."""
    started = time.monotonic()
    child_env = dict(os.environ)
    child_env.setdefault("PYTHONHASHSEED", "0")
    child_env.setdefault("PYTHONIOENCODING", "utf-8")
    if env:
        child_env.update(env)
    timed_out = False
    exit_code: int | None = None
    stdout = ""
    stderr = ""
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            shell=True,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_s,
            env=child_env,
        )
        exit_code = proc.returncode
        stdout = proc.stdout
        stderr = proc.stderr
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        stdout = exc.stdout or "" if isinstance(exc.stdout, str) else ""
        stderr = (exc.stderr or "") if isinstance(exc.stderr, str) else ""
    except OSError as exc:  # pragma: no cover - missing shell, permission errors
        stderr = f"{type(exc).__name__}: {exc}"
    duration = time.monotonic() - started
    return RunResult(
        cmd=cmd,
        cwd=str(cwd),
        timeout_s=timeout_s,
        exit_code=exit_code,
        timed_out=timed_out,
        duration_s=duration,
        stdout=stdout,
        stderr=stderr,
    )


Runner = Callable[[str, Path, float], RunResult]


@dataclass
class Outcome:
    """One claim's result. ``evidence`` must stay JSON-serialisable."""

    verdict: str
    reason: str
    evidence: dict[str, Any] = field(default_factory=dict)
    uncertainty: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.verdict not in VERDICTS:
            raise ValueError(f"unknown verdict: {self.verdict!r}")
        # A JSON round-trip both validates and normalises the payload.
        self.evidence = json.loads(canonical_json(self.evidence))
        if self.uncertainty is not None:
            self.uncertainty = json.loads(canonical_json(self.uncertainty))


@dataclass
class CheckContext:
    """Everything a checker is allowed to use for one claim."""

    claim: dict[str, Any]
    audit: dict[str, Any]
    audit_dir: Path
    runner: Runner
    policy: dict[str, Any] = field(default_factory=dict)

    @property
    def timeout_s(self) -> float:
        return float(self.policy.get("timeout_s", DEFAULT_TIMEOUT_S))

    def check_dir(self) -> Path:
        """Working directory for the claim's commands."""
        raw = self.claim.get("check", {}).get("cwd")
        if raw is None:
            return self.audit_dir
        return (self.audit_dir / raw).resolve()


class Checker(Protocol):
    """Protocol every checker module implements."""

    kind: str

    def check(self, ctx: CheckContext) -> Outcome:  # pragma: no cover - interface
        ...
