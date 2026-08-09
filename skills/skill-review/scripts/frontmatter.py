#!/usr/bin/env python3
"""
frontmatter.py - Parse and validate a skill's SKILL.md frontmatter.

Reuses the validation rules from skill-creator's quick_validate.py (name kebab-case,
description present, no angle brackets) and additionally extracts allowed-tools and
metadata.requires.bins for the audit. Emits frontmatter.json (schema in
references/isolation-contract.md).

Usage:
    frontmatter.py <skill_dir_or_SKILL.md> [--out frontmatter.json]

Tries PyYAML; falls back to a minimal line parser so it works with no third-party deps.
"""

import argparse
import json
import re
import sys
from pathlib import Path

NAME_RE = re.compile(r"^[a-z0-9-]+$")


def split_frontmatter(text: str):
    if not text.startswith("---"):
        return None
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    return m.group(1) if m else None


def parse_yaml(block: str) -> dict:
    try:
        import yaml  # type: ignore
        data = yaml.safe_load(block)
        return data if isinstance(data, dict) else {}
    except Exception:
        return minimal_parse(block)


def minimal_parse(block: str) -> dict:
    """Best-effort parser for the simple frontmatter we care about."""
    data = {}
    lines = block.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.lstrip().startswith("#"):
            i += 1
            continue
        m = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if not m:
            i += 1
            continue
        key, val = m.group(1), m.group(2).strip()
        if key == "metadata" and val == "":
            # capture nested requires.bins
            block_lines = []
            j = i + 1
            while j < len(lines) and (lines[j].startswith("  ") or not lines[j].strip()):
                block_lines.append(lines[j])
                j += 1
            data["metadata"] = parse_metadata("\n".join(block_lines))
            i = j
            continue
        if val and val[0] in "|>":
            # YAML block scalar (folded/literal): gather the indented continuation lines
            block_lines = []
            j = i + 1
            while j < len(lines) and (lines[j].startswith("  ") or not lines[j].strip()):
                block_lines.append(lines[j].strip())
                j += 1
            data[key] = " ".join(b for b in block_lines if b)
            i = j
            continue
        data[key] = strip_quotes(val)
        i += 1
    return data


def parse_metadata(block: str) -> dict:
    bins = []
    for m in re.finditer(r"bins?:\s*\[([^\]]*)\]", block):
        bins += [strip_quotes(x.strip()) for x in m.group(1).split(",") if x.strip()]
    # also handle YAML list form: bins:\n    - git
    if "bins:" in block and not bins:
        after = block.split("bins:", 1)[1]
        for m in re.finditer(r"^\s*-\s*(.+)$", after, re.MULTILINE):
            bins.append(strip_quotes(m.group(1).strip()))
    return {"requires": {"bins": bins}} if bins else {}


def strip_quotes(s: str) -> str:
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
        return s[1:-1]
    return s


def normalize_tools(val):
    if val is None:
        return []
    if isinstance(val, list):
        return [str(x) for x in val]
    return [t for t in re.split(r"[,\s]+", str(val).strip()) if t]


def get_bins(meta) -> list:
    if not isinstance(meta, dict):
        return []
    req = meta.get("requires")
    if isinstance(req, dict) and isinstance(req.get("bins"), list):
        return [str(b) for b in req["bins"]]
    return []


def validate_and_extract(skill_md: Path) -> dict:
    errors = []
    if not skill_md.exists():
        return {"valid": False, "errors": ["SKILL.md not found"]}
    text = skill_md.read_text(encoding="utf-8", errors="replace")
    block = split_frontmatter(text)
    if block is None:
        return {"valid": False, "errors": ["No YAML frontmatter found"]}
    data = parse_yaml(block)

    name = str(data.get("name", "")).strip()
    desc = data.get("description", "")
    desc = "" if desc is None else str(desc)

    if not name:
        errors.append("Missing 'name'")
    elif not NAME_RE.match(name):
        errors.append(f"Name '{name}' must be kebab-case (lowercase, digits, hyphens)")
    elif name.startswith("-") or name.endswith("-") or "--" in name:
        errors.append(f"Name '{name}' cannot start/end with hyphen or contain '--'")
    if len(name) > 64:
        errors.append("Name exceeds 64 chars")

    if not desc:
        errors.append("Missing 'description'")
    if "<" in desc or ">" in desc:
        errors.append("Description cannot contain angle brackets (< or >)")
    if len(desc) > 1024:
        errors.append("Description exceeds 1024 chars")

    return {
        "valid": not errors,
        "errors": errors,
        "name": name,
        "description": desc,
        "declared_allowed_tools": normalize_tools(data.get("allowed-tools")),
        "declared_bins": get_bins(data.get("metadata")),
        "description_len": len(desc),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Parse + validate SKILL.md frontmatter")
    ap.add_argument("target", help="skill dir or path to SKILL.md")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    p = Path(args.target)
    skill_md = p if p.name.upper() == "SKILL.MD" else p / "SKILL.md"
    result = validate_and_extract(skill_md)
    result = {"skill_name": result.get("name", skill_md.parent.name), **result}

    out = json.dumps(result, indent=2, ensure_ascii=False)
    if args.out:
        Path(args.out).write_text(out, encoding="utf-8")
        print(f"wrote {args.out} (valid={result['valid']})")
    else:
        print(out)
    return 0 if result.get("valid") else 2


if __name__ == "__main__":
    sys.exit(main())
