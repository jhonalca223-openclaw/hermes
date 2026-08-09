# Optional install-reminder hook

A belt-and-suspenders reminder that triggers when the agent is about to copy/install a skill
into a skills directory. **This is harness configuration, not part of the audit** — the skill
works without it (intent-based triggering via the SKILL.md description is the primary path).

## Install (Claude Code)

1. Find the absolute path to this skill, e.g.
   `D:/AI_Project/Skills/Myskills/skill-review/skill-review`.
2. In `settings.snippet.json`, replace `<ABS_PATH>` with that path.
3. Merge the `hooks` block into your `~/.claude/settings.json` (the **update-config** skill can
   do this for you). Keep any existing hooks.

When the agent runs a `Bash` copy/move/install command (or a `Write`/`Edit`) targeting
`~/.claude/skills`, `~/.agents/skills`, `~/.claude/plugins`, or any `*/skills/` path, the hook
prints a reminder to audit the skill first.

## Remind vs block

- Default: **reminder** (exit 0). The agent sees the note but is not blocked.
- To **block** until the user acknowledges: set `BLOCK=1` in the hook command's environment
  (`"command": "BLOCK=1 python ..."` on POSIX, or set it via your settings env). The guard
  then exits 2, which Claude Code treats as a blocking denial.

## Caveats

- The PreToolUse payload shape can differ across Claude Code versions; the guard fails open
  (exits 0) on any parse error so it never breaks your session. Verify behavior on your
  version before relying on the blocking mode.
- The matcher is conservative (copy/move/install verbs + a skills-dir path) to avoid noise,
  but it is heuristic — it is a nudge, not a guarantee.
