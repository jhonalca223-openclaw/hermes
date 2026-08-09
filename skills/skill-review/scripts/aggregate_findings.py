#!/usr/bin/env python3
"""
aggregate_findings.py - Merge per-reviewer findings into consolidated.json.

Combines finding.<role>.json files: de-dupes by (dimension, file, locator), unions
raised_by, bumps confidence to high when >=2 roles agree, cross-checks coverage against
manifest.json, optionally folds in dynamic.json, and runs the injection SANITIZER (default
ON) that strips any residual role markers / ignore-instructions / tool-call syntax that a
reviewer's paraphrase may have echoed from untrusted content.

Usage:
    aggregate_findings.py --manifest manifest.json [--dynamic dynamic.json]
                          [--no-sanitize] [--out consolidated.json]
                          finding.redteam.json finding.exfil.json ...

Pure stdlib.
"""

import argparse
import json
import re
import sys
from pathlib import Path

SEVS = ["critical", "high", "medium", "low", "info"]

# Sanitizer: neutralize injection artifacts that may survive in paraphrased text fields.
SANITIZE_RULES = [
    (re.compile(r"ignore (previous|all (prior|above)) instructions", re.I), "[redacted-injection]"),
    (re.compile(r"disregard (the above|your instructions)", re.I), "[redacted-injection]"),
    (re.compile(r"忽略(以上|上面|前面|之前)(的)?(所有)?(指令|提示)", ), "[redacted-injection]"),
    (re.compile(r"无视(之前|前面)的(指令|提示)"), "[redacted-injection]"),
    (re.compile(r"\[(SYSTEM|ADMIN|INST|ASSISTANT|USER)\]", re.I), "[redacted-marker]"),
    (re.compile(r"<\|im_(start|end)\|>"), "[redacted-marker]"),
    (re.compile(r"<function_calls>|</function_calls>|<invoke\b", re.I), "[redacted-toolcall]"),
    (re.compile(r"```tool_(use|call)", re.I), "[redacted-toolcall]"),
]
TEXT_FIELDS = ["title", "evidence_summary", "why_dangerous", "dual_use_assessment", "recommended_action"]


def sanitize_text(s, counter):
    if not isinstance(s, str):
        return s
    for rx, repl in SANITIZE_RULES:
        s, n = rx.subn(repl, s)
        counter[0] += n
    return s


def sanitize_finding(f, counter):
    for k in TEXT_FIELDS:
        if k in f:
            f[k] = sanitize_text(f[k], counter)
    return f


def sev_idx(s):
    return SEVS.index(s) if s in SEVS else SEVS.index("info")


def worst(a, b):
    return a if sev_idx(a) <= sev_idx(b) else b


def key_of(f):
    return (f.get("dimension"), f.get("file"), str(f.get("locator", "")).strip().lower())


def main() -> int:
    ap = argparse.ArgumentParser(description="Aggregate reviewer findings")
    ap.add_argument("findings", nargs="*", help="finding.<role>.json files")
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--dynamic", default=None)
    ap.add_argument("--no-sanitize", action="store_true")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    manifest_files = {f["path"] for f in manifest.get("files", [])}

    reviewers = []
    reviewed_union = set()
    gap_prefixes = set()
    merged = {}
    san_counter = [0]
    sanitize = not args.no_sanitize

    for fp in args.findings:
        data = json.loads(Path(fp).read_text(encoding="utf-8"))
        role = data.get("reviewer_role", Path(fp).stem)
        reviewers.append(role)
        reviewed_union.update(data.get("files_reviewed", []))
        for g in data.get("coverage_gaps", []):
            raw = str(g.get("file", "")).strip()
            tok = raw.split()[0] if raw else ""          # path token before any annotation
            tok = tok.replace("**", "").replace("*", "")
            if tok:
                gap_prefixes.add(tok)
        for f in data.get("findings", []):
            if sanitize:
                f = sanitize_finding(f, san_counter)
            if f.get("severity") not in SEVS:        # coerce malformed severity (never crash)
                f["severity"] = "info"
            k = key_of(f)
            if k in merged:
                m = merged[k]
                m["severity"] = worst(m["severity"], f.get("severity", "info"))
                if role not in m["raised_by"]:
                    m["raised_by"].append(role)
                m["forces_block"] = m.get("forces_block") or f.get("forces_block", False)
            else:
                f = dict(f)
                f["raised_by"] = [role]
                f["disputed"] = False
                f["dispute_notes"] = None
                merged[k] = f

    # confidence bump for multi-role agreement
    for f in merged.values():
        if len(f["raised_by"]) >= 2:
            f["confidence"] = "high"

    unreviewed = sorted(manifest_files - reviewed_union)
    # partition unreviewed files: covered by a directory/blob coverage-gap vs truly unreviewed
    by_gap = {}
    truly = []
    prefixes = sorted(gap_prefixes, key=len, reverse=True)
    for path in unreviewed:
        matched = next((p for p in prefixes if path == p or path.startswith(p.rstrip("/") + "/")), None)
        if matched:
            by_gap[matched] = by_gap.get(matched, 0) + 1
        else:
            truly.append(path)

    findings = list(merged.values())
    blob_gaps = []
    # one summary finding per blob/dir coverage-gap that actually covers multiple files
    for prefix, n in sorted(by_gap.items()):
        if n < 2:
            continue  # a single concrete file (e.g. one binary) — not a blob
        blob_gaps.append({"prefix": prefix, "file_count": n})
        findings.append({
            "id": f"COV-BLOB-{prefix.strip('/').replace('/', '_') or 'root'}",
            "dimension": "intent_mismatch", "severity": "low", "confidence": "low",
            "file": prefix, "locator": f"{n} files",
            "title": f"{n} files under {prefix} not individually reviewed (bundled-blob coverage gap)",
            "evidence_summary": f"{n} manifest files under {prefix} were recorded by a reviewer as a bundled blob and not line-by-line analyzed.",
            "why_dangerous": "Bundled, un-individually-reviewed files can hide undisclosed behavior; assess the bundle's necessity, provenance, and whether it should ship at all.",
            "raised_by": ["aggregator"], "disputed": False, "forces_block": False,
            "recommended_action": "caution",
        })
    # per-file finding only for genuinely unreviewed files (nothing silently skipped)
    for path in truly:
        findings.append({
            "id": f"COV-{path}", "dimension": "intent_mismatch", "severity": "low",
            "confidence": "low", "file": path, "locator": "whole file",
            "title": "File not covered by any reviewer",
            "evidence_summary": "This manifest file was not in any reviewer's files_reviewed set or coverage gaps.",
            "why_dangerous": "Unreviewed files can hide undisclosed behavior.",
            "raised_by": ["aggregator"], "disputed": False, "forces_block": False,
            "recommended_action": "caution",
        })
    unreviewed = truly

    counts = {s: 0 for s in SEVS}
    for f in findings:
        counts[f.get("severity", "info")] = counts.get(f.get("severity", "info"), 0) + 1

    dynamic = None
    if args.dynamic and Path(args.dynamic).exists():
        dynamic = json.loads(Path(args.dynamic).read_text(encoding="utf-8"))

    findings.sort(key=lambda f: SEVS.index(f.get("severity", "info")))

    result = {
        "skill_name": manifest.get("skill_name"),
        "skill_path": manifest.get("skill_path"),
        "runtime": manifest.get("runtime"),
        "reviewers_run": reviewers,
        "manifest_file_count": len(manifest_files),
        "reviewed_union": sorted(reviewed_union),
        "unreviewed_files": unreviewed,
        "blob_coverage_gaps": blob_gaps,
        "findings": findings,
        "counts": counts,
        "dynamic": dynamic,
        "sanitizer_applied": sanitize,
        "sanitizer_removed": san_counter[0],
    }

    out = json.dumps(result, indent=2, ensure_ascii=False)
    if args.out:
        Path(args.out).write_text(out, encoding="utf-8")
        print(f"wrote {args.out} (findings={len(findings)}, counts={counts}, "
              f"sanitized={san_counter[0]})")
    else:
        print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
