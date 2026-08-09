#!/usr/bin/env python3
"""
package_dist.py - Package skill-review into a distributable zip, with an option to exclude
the self-test fixtures (which contain intentionally malicious sample code that can trip
antivirus heuristics on a recipient's machine).

Validates frontmatter first (via frontmatter.py), then zips. Always excludes runtime cruft
(__pycache__, _run, _smoke, dist, .DS_Store). With --no-fixtures it also drops tests/.

Usage:
    package_dist.py [--skill .] [--out dist] [--no-fixtures]

Pure stdlib.
"""

import argparse
import json
import subprocess
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ALWAYS_EXCLUDE = {"dist", ".git"}
ALWAYS_EXCLUDE_NAMES = {".DS_Store"}


def excluded(rel: Path, drop_tests: bool) -> bool:
    parts = rel.parts
    # skip anything under an underscore-prefixed dir (_run, _smoke, _wtrun, __pycache__, ...)
    # but keep files like scripts/__init__.py (only PARENT components are checked)
    for p in parts[:-1]:
        if p.startswith("_"):
            return True
    if set(parts) & ALWAYS_EXCLUDE:
        return True
    if parts and parts[-1] in ALWAYS_EXCLUDE_NAMES:
        return True
    if drop_tests and parts and parts[0] == "tests":
        return True
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description="Package skill-review for distribution")
    ap.add_argument("--skill", default=str(HERE.parent), help="skill root (default: this skill)")
    ap.add_argument("--out", default="dist", help="output directory")
    ap.add_argument("--no-fixtures", action="store_true",
                    help="exclude tests/ (AV-friendly; recipients lose self-test fixtures)")
    args = ap.parse_args()

    skill = Path(args.skill).resolve()
    if not (skill / "SKILL.md").exists():
        print(f"error: no SKILL.md in {skill}", file=sys.stderr)
        return 1

    # validate frontmatter
    fm = subprocess.run([sys.executable, str(HERE / "frontmatter.py"), str(skill)],
                        capture_output=True, text=True, encoding="utf-8")
    try:
        data = json.loads(fm.stdout)
    except Exception:
        print(f"error: frontmatter check failed:\n{fm.stdout}\n{fm.stderr}", file=sys.stderr)
        return 1
    if not data.get("valid"):
        print(f"validation failed: {data.get('errors')}", file=sys.stderr)
        return 1
    print(f"validated: {data['name']} (description {data['description_len']} chars)")

    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    suffix = "-nofixtures" if args.no_fixtures else ""
    zip_path = out_dir / f"{skill.name}{suffix}.zip"

    n = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(skill.rglob("*")):
            if not f.is_file():
                continue
            rel = f.relative_to(skill)
            if excluded(rel, args.no_fixtures):
                continue
            z.write(f, Path(skill.name) / rel)
            n += 1
    print(f"wrote {zip_path} ({n} files, fixtures={'excluded' if args.no_fixtures else 'included'})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
