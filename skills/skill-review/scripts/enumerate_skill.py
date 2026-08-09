#!/usr/bin/env python3
"""
enumerate_skill.py - Deterministic file inventory of a skill under audit.

Walks a skill directory, classifies every file, hashes it, flags symlinks that
escape the skill root, and emits manifest.json (schema in references/isolation-contract.md).
This guarantees full coverage: reviewers must account for every file listed here.

Usage:
    enumerate_skill.py <skill_dir> [--out manifest.json] [--runtime NAME]

Pure stdlib. Cross-platform (pathlib, explicit utf-8). Never executes skill code.
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

EXEC_EXT = {".py", ".sh", ".bash", ".zsh", ".ps1", ".psm1", ".bat", ".cmd",
            ".js", ".mjs", ".cjs", ".rb", ".pl", ".php", ".ts"}
SCRIPT_EXT = EXEC_EXT | {".com"}


def classify(rel: Path, is_binary: bool) -> str:
    parts = [p.lower() for p in rel.parts]
    name = rel.name.lower()
    ext = rel.suffix.lower()
    if name == "skill.md" and len(rel.parts) == 1:
        return "skill_md"
    if is_binary:
        return "binary"
    top = parts[0] if parts else ""
    if top == "agents" or "reviewers" in parts:
        return "agent"
    if top == "scripts" or ext in SCRIPT_EXT:
        return "script"
    if top == "references":
        return "reference"
    if top == "assets":
        return "asset"
    if top in ("evals", "tests"):
        return "eval"
    if ext == ".json":
        return "config"
    if ext in (".md", ".txt", ".rst"):
        return "reference"
    return "other"


def looks_binary(path: Path) -> bool:
    try:
        chunk = path.read_bytes()[:4096]
    except OSError:
        return True
    if b"\x00" in chunk:
        return True
    try:
        chunk.decode("utf-8")
        return False
    except UnicodeDecodeError:
        return True


def has_shebang(path: Path) -> bool:
    try:
        with path.open("rb") as fh:
            return fh.read(2) == b"#!"
    except OSError:
        return False


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    try:
        with path.open("rb") as fh:
            for block in iter(lambda: fh.read(65536), b""):
                h.update(block)
    except OSError:
        return ""
    return h.hexdigest()


def enumerate_skill(skill_dir: Path, runtime: str) -> dict:
    root = skill_dir.resolve()
    files = []
    symlink_escapes = []
    total = 0

    for path in sorted(root.rglob("*")):
        if path.is_dir():
            continue
        rel = path.relative_to(root)
        is_symlink = path.is_symlink()
        escapes = False
        target = None
        if is_symlink:
            try:
                target = str(path.resolve())
                escapes = root not in path.resolve().parents and path.resolve() != root
            except OSError:
                escapes = True
        else:
            # non-symlink files come from root.rglob, so they are always under root
            escapes = False
        is_bin = looks_binary(path)
        size = path.stat().st_size if path.exists() else 0
        total += size
        ext = path.suffix.lower()
        entry = {
            "path": str(rel).replace("\\", "/"),
            "class": classify(rel, is_bin),
            "bytes": size,
            "sha256": sha256_of(path),
            "is_executable": ext in EXEC_EXT or has_shebang(path),
            "is_binary": is_bin,
            "is_symlink": is_symlink,
            "symlink_target": target,
            "escapes_root": escapes,
        }
        files.append(entry)
        if escapes:
            symlink_escapes.append(entry["path"])

    name = root.name
    skill_md = root / "SKILL.md"
    if skill_md.exists():
        try:
            head = skill_md.read_text(encoding="utf-8", errors="replace")
            import re
            m = re.search(r"^name:\s*(.+)$", head, re.MULTILINE)
            if m:
                name = m.group(1).strip().strip('"').strip("'")
        except OSError:
            pass

    return {
        "skill_name": name,
        "skill_path": str(root).replace("\\", "/"),
        "runtime": runtime,
        "file_count": len(files),
        "files": files,
        "total_bytes": total,
        "symlink_escapes": symlink_escapes,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Enumerate a skill's files into manifest.json")
    ap.add_argument("skill_dir")
    ap.add_argument("--out", default=None, help="output path (default: stdout)")
    ap.add_argument("--runtime", default="unknown")
    args = ap.parse_args()

    skill_dir = Path(args.skill_dir)
    if not skill_dir.exists():
        print(f"error: skill dir not found: {skill_dir}", file=sys.stderr)
        return 1

    manifest = enumerate_skill(skill_dir, args.runtime)
    out = json.dumps(manifest, indent=2, ensure_ascii=False)
    if args.out:
        Path(args.out).write_text(out, encoding="utf-8")
        print(f"wrote {args.out} ({manifest['file_count']} files, "
              f"{len(manifest['symlink_escapes'])} symlink escapes)")
    else:
        print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
