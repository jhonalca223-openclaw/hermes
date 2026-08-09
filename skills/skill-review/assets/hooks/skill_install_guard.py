#!/usr/bin/env python3
"""
skill_install_guard.py - Optional PreToolUse hook: remind the agent to run skill-review
before a skill is copied into a skills directory.

Reads the hook payload as JSON on stdin (Claude Code PreToolUse shape:
{"tool_name": "...", "tool_input": {"command": "...", "file_path": "..."}}), checks whether
the action targets a skills directory, and if so prints a reminder to stderr.

Exit code:
  0  -> informational reminder (non-blocking).  [default]
  2  -> set BLOCK=1 in env to instead block the tool call and surface the reminder.

This is harness configuration, not part of the skill's audit logic. Verify the exact hook
payload shape for your runtime/version before relying on blocking behavior.
"""

import json
import os
import re
import sys

SKILL_DIR_RE = re.compile(
    r"(\.claude[/\\]skills|\.agents[/\\]skills|\.claude[/\\]plugins|[/\\]skills[/\\])",
    re.IGNORECASE,
)


def targets_skill_dir(payload: dict) -> str:
    ti = payload.get("tool_input", {}) or {}
    blobs = []
    for k in ("command", "file_path", "path", "content"):
        v = ti.get(k)
        if isinstance(v, str):
            blobs.append(v)
    text = "\n".join(blobs)
    # Only fire when it looks like a copy/move/write INTO a skills dir
    if SKILL_DIR_RE.search(text) and re.search(
        r"\b(cp|copy|move|mv|Copy-Item|Move-Item|install|add|extract|unzip|write)\b",
        text, re.IGNORECASE,
    ):
        return text
    # Write tool directly targeting a skills dir
    if payload.get("tool_name") in ("Write", "Edit") and SKILL_DIR_RE.search(text):
        return text
    return ""


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0  # never break the host on a parse error
    hit = targets_skill_dir(payload)
    if not hit:
        return 0
    msg = ("[skill-review] This action looks like it installs/copies a skill into a skills "
           "directory. Untrusted skills can carry malware, data-exfiltration, or "
           "prompt-injection. Recommend auditing it first: run the skill-review skill on the "
           "candidate folder (stage it outside the skills dir and get a PASS/WARN/BLOCK "
           "verdict) before it goes live.")
    print(msg, file=sys.stderr)
    return 2 if os.environ.get("BLOCK") == "1" else 0


if __name__ == "__main__":
    sys.exit(main())
