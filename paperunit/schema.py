"""Audit specification loading, migration and validation (schema ``paperunit/v1``).

The audit file is the unit of preregistration: it states the target, the scope,
and one entry per claim, each bound to a check spec.  Validation here is
structural only; semantics belong to the individual checkers.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SCHEMA_V1 = "paperunit/v1"
SUPPORTED_SCHEMAS = (SCHEMA_V1,)
LEGACY_SCHEMA_MAP = {"paperaudit/v0": SCHEMA_V1}


class AuditSpecError(Exception):
    """Raised when an audit file is malformed or uses an unsupported schema."""


def load_audit(path: str | Path) -> dict[str, Any]:
    """Read, migrate (if legacy) and validate one audit file."""
    audit_path = Path(path)
    try:
        raw = json.loads(audit_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise AuditSpecError(f"audit file not found: {audit_path}") from exc
    except json.JSONDecodeError as exc:
        raise AuditSpecError(f"audit file is not valid JSON: {audit_path}: {exc}") from exc
    audit = migrate_audit(raw, audit_path)
    validate_audit(audit, audit_path)
    return audit


def migrate_audit(raw: dict[str, Any], path: Path) -> dict[str, Any]:
    """Bring legacy schemas forward. The v0 format is structurally identical."""
    if not isinstance(raw, dict):
        raise AuditSpecError(f"audit must be a JSON object: {path}")
    schema = raw.get("schema")
    if schema in LEGACY_SCHEMA_MAP:
        migrated = dict(raw)
        migrated["schema"] = LEGACY_SCHEMA_MAP[schema]
        migrated.setdefault("target", {})
        migrated["target"] = dict(migrated["target"])
        migrated["target"].setdefault("migrated_from", schema)
        return migrated
    return raw


def validate_audit(audit: dict[str, Any], path: Path | None = None) -> None:
    where = f" ({path})" if path else ""
    schema = audit.get("schema")
    if schema not in SUPPORTED_SCHEMAS:
        raise AuditSpecError(
            f"unsupported schema {schema!r}{where}; expected one of {SUPPORTED_SCHEMAS}"
        )
    target = audit.get("target")
    if not isinstance(target, dict):
        raise AuditSpecError(f"'target' must be an object{where}")
    for field in ("title", "audited_by", "date"):
        if not isinstance(target.get(field), str) or not target[field].strip():
            raise AuditSpecError(f"'target.{field}' must be a non-empty string{where}")
    scope = audit.get("scope", {})
    if scope is not None and not isinstance(scope, dict):
        raise AuditSpecError(f"'scope' must be an object{where}")
    for field in ("tested", "not_tested"):
        values = (scope or {}).get(field, [])
        if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
            raise AuditSpecError(f"'scope.{field}' must be a list of strings{where}")
    claims = audit.get("claims")
    if not isinstance(claims, list) or not claims:
        raise AuditSpecError(f"'claims' must be a non-empty list{where}")
    seen: set[str] = set()
    for index, claim in enumerate(claims):
        if not isinstance(claim, dict):
            raise AuditSpecError(f"claims[{index}] must be an object{where}")
        cid = claim.get("id")
        if not isinstance(cid, str) or not cid.strip():
            raise AuditSpecError(f"claims[{index}].id must be a non-empty string{where}")
        if cid in seen:
            raise AuditSpecError(f"duplicate claim id {cid!r}{where}")
        seen.add(cid)
        if not isinstance(claim.get("kind"), str) or not claim["kind"].strip():
            raise AuditSpecError(f"claims[{index}].kind must be a non-empty string{where}")
        if claim["kind"] != "human" and not isinstance(claim.get("check"), dict):
            raise AuditSpecError(f"claims[{index}] ('{cid}') needs a 'check' object{where}")
        if "text" in claim and not isinstance(claim["text"], str):
            raise AuditSpecError(f"claims[{index}].text must be a string{where}")
