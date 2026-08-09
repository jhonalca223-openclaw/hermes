#!/usr/bin/env python3
"""
discover_skills.py - Cross-runtime discovery of installed skills.

Reads references/runtime-profiles.json, expands each runtime's skill_roots (~ and globs),
finds every child dir containing SKILL.md, resolves symlinks, dedupes by realpath, and
emits an inventory plus a {name, description} metadata catalog (for the conflict reviewer).
Also resolves <WORKDIR> and asserts it sits OUTSIDE all skill roots.

Usage:
    discover_skills.py [--runtime NAME|all] [--root DIR ...] [--workspace DIR]
                       [--workdir DIR] [--out inventory.json] [--catalog catalog.json]

Pure stdlib.
"""

import argparse
import glob as globmod
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROFILES = HERE.parent / "references" / "runtime-profiles.json"


def load_profiles() -> dict:
    return json.loads(PROFILES.read_text(encoding="utf-8"))


def expand(path: str, workspace: Path):
    """Expand ~ and relative ./ roots, then glob. Returns list of existing dirs."""
    raw = path
    if raw.startswith("~"):
        raw = str(Path.home() / raw[2:]) if raw[1:2] in ("/", "\\") else str(Path.home())
        if path != "~":
            raw = os.path.expanduser(path)
    elif raw.startswith("./") or raw.startswith(".\\"):
        raw = str(workspace / raw[2:])
    raw = os.path.expanduser(raw)
    matches = globmod.glob(raw) if any(c in raw for c in "*?[") else [raw]
    return [Path(m) for m in matches if Path(m).is_dir()]


def detect_host(profiles: dict) -> str:
    for prof in profiles["profiles"]:
        det = prof.get("detect", {})
        if any(os.environ.get(e) for e in det.get("env", [])):
            return prof["name"]
    for prof in profiles["profiles"]:
        det = prof.get("detect", {})
        for p in det.get("paths", []):
            if Path(os.path.expanduser(p)).exists():
                return prof["name"]
    return "generic"


def read_meta(skill_md: Path):
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None, None
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    block = m.group(1) if m else text[:2000]
    name = None
    desc = None
    nm = re.search(r"^name:\s*(.+)$", block, re.MULTILINE)
    if nm:
        name = nm.group(1).strip().strip('"').strip("'")
    dm = re.search(r"^description:\s*(.+)$", block, re.MULTILINE)
    if dm:
        desc = dm.group(1).strip().strip('"').strip("'")
    return name, desc


def collect_roots(profiles, runtime, extra_roots, workspace):
    chosen = []
    names = [p["name"] for p in profiles["profiles"]]
    targets = names if runtime == "all" else [runtime]
    for prof in profiles["profiles"]:
        if prof["name"] not in targets:
            continue
        for r in prof.get("skill_roots", []):
            for d in expand(r["path"], workspace):
                chosen.append((prof["name"], d))
    for r in extra_roots:
        for d in expand(r, workspace):
            chosen.append(("custom", d))
    # auto-probe under workspace
    if workspace and workspace.is_dir():
        for pat in profiles.get("auto_probe_patterns", []):
            for m in globmod.glob(str(workspace / pat)):
                if Path(m).is_dir():
                    chosen.append(("probe", Path(m)))
    return chosen


def discover(roots):
    """Each root is a dir whose children may be skills, or which is itself a skill."""
    seen = {}
    for runtime, root in roots:
        candidates = []
        if (root / "SKILL.md").exists():
            candidates.append(root)
        for child in sorted(root.iterdir()) if root.is_dir() else []:
            if child.is_dir() and (child / "SKILL.md").exists():
                candidates.append(child)
        for c in candidates:
            try:
                rp = str(c.resolve())
            except OSError:
                rp = str(c)
            if rp in seen:
                seen[rp]["roots_seen"].append({"runtime": runtime, "via": str(root)})
                continue
            name, desc = read_meta(c / "SKILL.md")
            seen[rp] = {
                "skill_name": name or c.name,
                "path": str(c).replace("\\", "/"),
                "realpath": rp.replace("\\", "/"),
                "description": desc or "",
                "roots_seen": [{"runtime": runtime, "via": str(root)}],
            }
    return list(seen.values())


def workdir_check(workdir: Path, roots) -> dict:
    wd = workdir.resolve()
    inside = []
    for _, root in roots:
        try:
            rr = root.resolve()
            if wd == rr or rr in wd.parents:
                inside.append(str(rr))
        except OSError:
            continue
    return {"workdir": str(wd).replace("\\", "/"),
            "inside_skill_root": inside,
            "ok": not inside}


def resolve_workdir(arg, profiles, host):
    if arg:
        return Path(os.path.expanduser(arg))
    if os.environ.get("SKILL_REVIEW_HOME"):
        return Path(os.path.expanduser(os.environ["SKILL_REVIEW_HOME"]))
    for prof in profiles["profiles"]:
        if prof["name"] == host:
            return Path(os.path.expanduser(prof["work_dir"]))
    return Path(os.path.expanduser("~/.skill-review"))


def main() -> int:
    ap = argparse.ArgumentParser(description="Discover installed skills across runtimes")
    ap.add_argument("--runtime", default="auto",
                    help="profile name, 'all', or 'auto' (detect host)")
    ap.add_argument("--root", action="append", default=[], help="extra skills dir(s)")
    ap.add_argument("--workspace", default=".", help="workspace root for ./ and auto-probe")
    ap.add_argument("--workdir", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--catalog", default=None)
    args = ap.parse_args()

    profiles = load_profiles()
    host = detect_host(profiles)
    runtime = host if args.runtime == "auto" else args.runtime
    workspace = Path(args.workspace).resolve()

    roots = collect_roots(profiles, runtime, args.root, workspace)
    skills = discover(roots)

    workdir = resolve_workdir(args.workdir, profiles, host)
    wd_check = workdir_check(workdir, roots)

    result = {
        "host_runtime": host,
        "scanned_runtime": runtime,
        "roots": [str(r).replace("\\", "/") for _, r in roots],
        "skill_count": len(skills),
        "skills": skills,
        "workdir_check": wd_check,
    }
    out = json.dumps(result, indent=2, ensure_ascii=False)
    if args.out:
        Path(args.out).write_text(out, encoding="utf-8")
        print(f"wrote {args.out} ({len(skills)} skills; host={host}; "
              f"workdir_ok={wd_check['ok']})")
    else:
        print(out)

    if args.catalog:
        catalog = [{"name": s["skill_name"], "description": s["description"]}
                   for s in skills]
        Path(args.catalog).write_text(
            json.dumps(catalog, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"wrote {args.catalog} ({len(catalog)} entries)")

    if not wd_check["ok"]:
        print(f"WARNING: <WORKDIR> {wd_check['workdir']} is inside a skill root "
              f"{wd_check['inside_skill_root']} - choose another --workdir", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
