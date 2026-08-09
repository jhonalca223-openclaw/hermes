#!/usr/bin/env python3
"""
validate_findings.py - Enforced OUTPUT gate for reviewer subagents (isolation hardening).

The orchestrator pipes every reviewer's finding.<role>.json through this BEFORE trusting it.
It hard-rejects anything that is not strict finding-schema JSON, so "return only structured
JSON" becomes code-enforced rather than a request the reviewer might ignore. Specifically it:
  - requires the top-level + per-finding schema (keys, enum values);
  - caps evidence_summary at 240 chars (a finding cannot smuggle a large verbatim blob);
  - rejects fields containing tool-call syntax, role markers, or fenced code blocks
    (an injection cannot ride a finding back into the orchestrator);
  - is the last line of defence after the aggregator's sanitizer.

Exit 0 = valid (prints normalized JSON). Exit 2 = invalid (prints errors). The orchestrator
must reject/re-request a reviewer whose output fails here.

Usage:
    validate_findings.py <finding.json> [--out normalized.json]
    cat finding.json | validate_findings.py -

Pure stdlib.
"""

import argparse
import json
import re
import sys
from pathlib import Path

DIMS = {"intent_mismatch", "data_exfiltration", "unauthorized_access", "dangerous_command",
        "prompt_injection", "skill_conflict", "provenance"}
SEVS = {"critical", "high", "medium", "low", "info"}
CONF = {"high", "medium", "low"}
ACTIONS = {"block", "caution", "ok"}
ROLES = {"redteam", "exfil-privacy", "injection", "conflict", "synthesizer", "aggregator"}
VERDICTS = {"block", "caution", "allow"}

SMUGGLE = re.compile(
    r"<\s*invoke\b|</?\s*function_calls\s*>|<\|im_(start|end)\|>|```|"
    r"\[(SYSTEM|ADMIN|ASSISTANT|USER|INST)\]|ignore\b.{0,25}\binstructions|"
    r"disregard (the above|your instructions)|忽略(以上|上面|前面|之前)|无视(之前|前面)",
    re.IGNORECASE)
TEXT_FIELDS = ["title", "evidence_summary", "why_dangerous", "dual_use_assessment"]


def check_text(val, field, fid, errors):
    if val is None:
        return
    if not isinstance(val, str):
        errors.append(f"{fid}.{field}: must be a string")
        return
    if field == "evidence_summary" and len(val) > 240:
        errors.append(f"{fid}.evidence_summary: {len(val)} chars exceeds 240 cap")
    if SMUGGLE.search(val):
        errors.append(f"{fid}.{field}: contains tool-call/role-marker/injection syntax "
                      "(possible passthrough) - reviewer must paraphrase")


def validate(data: dict) -> list:
    errors = []
    if not isinstance(data, dict):
        return ["top level is not a JSON object"]
    role = data.get("reviewer_role")
    if role not in ROLES:
        errors.append(f"reviewer_role '{role}' not in {sorted(ROLES)}")
    if not isinstance(data.get("files_reviewed"), list):
        errors.append("files_reviewed must be a list")
    pv = data.get("perspective_verdict")
    if role != "synthesizer" and pv not in VERDICTS:
        errors.append(f"perspective_verdict '{pv}' not in {sorted(VERDICTS)}")
    findings = data.get("findings")
    if not isinstance(findings, list):
        return errors + ["findings must be a list"]
    for i, f in enumerate(findings):
        fid = f.get("id", f"finding[{i}]") if isinstance(f, dict) else f"finding[{i}]"
        if not isinstance(f, dict):
            errors.append(f"{fid}: not an object")
            continue
        if f.get("dimension") not in DIMS:
            errors.append(f"{fid}.dimension '{f.get('dimension')}' invalid")
        if f.get("severity") not in SEVS:
            errors.append(f"{fid}.severity '{f.get('severity')}' invalid")
        if "confidence" in f and f.get("confidence") not in CONF:
            errors.append(f"{fid}.confidence '{f.get('confidence')}' invalid")
        if "recommended_action" in f and f.get("recommended_action") not in ACTIONS:
            errors.append(f"{fid}.recommended_action '{f.get('recommended_action')}' invalid")
        if "forces_block" in f and not isinstance(f.get("forces_block"), bool):
            errors.append(f"{fid}.forces_block must be boolean")
        for fld in ("file", "locator"):
            if fld in f and not isinstance(f.get(fld), str):
                errors.append(f"{fid}.{fld}: must be a string pointer")
        for fld in TEXT_FIELDS:
            if fld in f:
                check_text(f.get(fld), fld, fid, errors)
    return errors


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate a reviewer finding file")
    ap.add_argument("path", help="finding json file, or - for stdin")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    raw = sys.stdin.read() if args.path == "-" else Path(args.path).read_text(encoding="utf-8")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"REJECT: not valid JSON ({e})", file=sys.stderr)
        return 2

    errors = validate(data)
    if errors:
        print("REJECT - reviewer output failed the schema gate:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 2

    norm = json.dumps(data, indent=2, ensure_ascii=False)
    if args.out:
        Path(args.out).write_text(norm, encoding="utf-8")
        print(f"OK: {args.path} valid ({len(data.get('findings', []))} findings)")
    else:
        print(norm)
    return 0


if __name__ == "__main__":
    sys.exit(main())
