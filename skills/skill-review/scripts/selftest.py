#!/usr/bin/env python3
"""
selftest.py - Validate the deterministic signature layer against tests/fixtures/.

For each fixture it runs prescan.py, collects the signal families, and checks them against
tests/fixtures/expectations.json:
  - malicious fixtures must surface every `must_families` entry (recall).
  - benign fixtures must surface none of their `forbidden_families` (precision proxy).

This exercises the deterministic layer only; the full PASS/WARN/BLOCK verdict needs the LLM
reviewer subagents (run via SKILL.md). Exit code is non-zero if any check fails.

Usage:
    selftest.py [--fixtures tests/fixtures]
"""

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRESCAN = HERE / "prescan.py"


def families_for(skill_dir: Path) -> set:
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "p.json"
        r = subprocess.run(
            [sys.executable, str(PRESCAN), str(skill_dir), "--out", str(out)],
            capture_output=True, text=True, encoding="utf-8",
            env={**__import__("os").environ, "PYTHONUTF8": "1"},
        )
        if r.returncode != 0:
            print(f"  prescan failed: {r.stderr.strip()}", file=sys.stderr)
            return set()
        data = json.loads(out.read_text(encoding="utf-8"))
    return {s["signal_family"] for s in data["signals"]}


def main() -> int:
    ap = argparse.ArgumentParser(description="Deterministic self-test")
    ap.add_argument("--fixtures", default=str(HERE.parent / "tests" / "fixtures"))
    args = ap.parse_args()

    fx = Path(args.fixtures)
    exp = json.loads((fx / "expectations.json").read_text(encoding="utf-8"))

    failures = []
    mal_pass = 0
    mal_total = 0
    ben_pass = 0
    ben_total = 0

    print("=== malicious (recall) ===")
    for name, spec in exp["malicious"].items():
        d = fx / "malicious" / name
        if not d.exists():
            failures.append(f"missing fixture: {d}")
            continue
        mal_total += 1
        fams = families_for(d)
        must = set(spec["must_families"])
        missing = must - fams
        ok = not missing
        mal_pass += ok
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}: families={sorted(fams)}"
              + ("" if ok else f"  MISSING {sorted(missing)}"))
        if not ok:
            failures.append(f"malicious {name} missing {sorted(missing)}")

    print("=== benign (precision) ===")
    for name, spec in exp["benign"].items():
        d = fx / "benign" / name
        if not d.exists():
            failures.append(f"missing fixture: {d}")
            continue
        ben_total += 1
        fams = families_for(d)
        forbidden = set(spec["forbidden_families"])
        tripped = forbidden & fams
        ok = not tripped
        ben_pass += ok
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}: families={sorted(fams)}"
              + ("" if ok else f"  TRIPPED {sorted(tripped)}"))
        if not ok:
            failures.append(f"benign {name} tripped {sorted(tripped)}")

    recall = mal_pass / mal_total if mal_total else 0
    precision = ben_pass / ben_total if ben_total else 0
    print(f"\nrecall (malicious caught):   {mal_pass}/{mal_total} = {recall:.0%}")
    print(f"precision (benign clean):    {ben_pass}/{ben_total} = {precision:.0%}")
    print("NOTE: directional REGRESSION metric on fixtures authored with the signatures — "
          "NOT real-world recall. See references/limitations.md.")

    if failures:
        print("\nFAILURES:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("\nall self-tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
