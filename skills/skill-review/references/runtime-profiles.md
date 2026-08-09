# Runtime Profiles (cross-runtime compatibility)

`skill-review` is not bound to Claude Code. A runtime profile (`runtime-profiles.json`,
read by `discover_skills.py` and the orchestrator) captures what differs between agent
runtimes. Built-in profiles: **claude-code, openclaw, codex, hermes, generic**.

## A profile serves two distinct purposes

1. **Where skills live (`skill_roots`)** — used for *discovery* in Mode B. Discovery may
   union the roots of **all** runtimes (cross-runtime scan) regardless of which runtime is
   currently hosting skill-review.
2. **What this runtime is like as a host (`subagent_support`, `work_dir`)** — used only for
   the **one** profile that matches the runtime *currently running skill-review*. It drives
   the isolation mode (subagents vs sequential fallback) and where the skill keeps its own
   working files.

These are independent: you can run skill-review under Claude Code and still discover +
audit skills installed for openclaw or Codex.

## Fields

| Field | Meaning |
|---|---|
| `name` | Profile id. |
| `detect` | Hints to auto-detect the host runtime: env vars and marker paths. |
| `skill_roots[]` | `{path, kind, needs_verification}`. `path` may use `~` and glob segments. `kind`: `flat` (each child dir is a skill) or `glob` (expand the pattern, each match is a skills dir). |
| `skill_format` | Skill file convention (all built-ins use `SKILL.md`). |
| `subagent_support` | `true` / `false` / `"unknown"`. Decides isolation mode when this runtime is the host (see below). |
| `work_dir` | This runtime's default `<WORKDIR>` (staging/quarantine/reports/manifest). |
| `install_cmd_hint` | Human hint for where a vetted skill should be placed. |

## Host-runtime detection (which profile am I running under?)

Resolve the host profile in this order, first match wins:
1. Explicit `--runtime <name>` argument / user statement.
2. `detect.env` — any listed env var is set.
3. `detect.paths` — a marker path exists.
4. Fall back to `generic`.

## Isolation mode from `subagent_support`

- `true` → parallel isolated reviewer subagents (preferred).
- `false` → single-context **sequential fallback** (see isolation-contract.md); report
  carries the `⚠ strict isolation not enforced` banner.
- `"unknown"` → probe the actual host: if the runtime can spawn a subagent here, treat as
  `true`; otherwise use the sequential fallback and note the uncertainty in the report.
  Never assume isolation you cannot demonstrate.

## `<WORKDIR>` resolution

Priority: `--workdir` arg > `$SKILL_REVIEW_HOME` env > host profile `work_dir` > generic
default `~/.skill-review`. **Hard invariant:** `<WORKDIR>` (and its `staging/` and
`quarantine/`) must resolve **outside every `skill_root` of the host runtime**, so a staged
or quarantined skill is never auto-discovered/triggered by that runtime while under review.
`discover_skills.py` verifies this and refuses a `<WORKDIR>` that sits inside a skill root.

## Discovery behavior (`discover_skills.py`)

1. For the chosen runtime(s), expand `skill_roots` (`~` via `Path.home()`, globs via
   `glob`), skipping non-existent roots without error.
2. Each immediate child dir containing a `SKILL.md` is a candidate skill.
3. Optionally auto-probe `auto_probe_patterns` under a `--workspace` to catch unregistered
   layouts.
4. Resolve symlinks and **dedupe by realpath** (e.g. Claude Code's `~/.claude/skills`
   symlinks many `lark-*` into `~/.agents/skills` — audit each once).
5. Emit an inventory `{skill_name, path, realpath, runtime, roots_seen[]}` plus a
   metadata catalog `{name, description}` (for the conflict reviewer).

## Adding / fixing a profile

Entries with `needs_verification: true` are best guesses. To harden one: confirm the
runtime's real skill root and subagent capability, then update `runtime-profiles.json`.
Until verified, rely on `generic` + `--root <dir>` and the auto-probe patterns.

Status of the built-in profiles:
- **Claude Code** — verified (`~/.claude/skills`, `~/.agents/skills`, plugin marketplaces).
- **openclaw** — verified layout (`.agents/skills`, `extensions/*/skills`, `skills`).
- **Codex** — `.codex/skills` (workspace) and `~/.codex/skills` (home) confirmed; the
  plugin/marketplace globs remain `needs_verification`.
- **Hermes** — `$HERMES_HOME/skills` (default `~/.hermes/skills`; eval homes
  `~/.hermes-test*/skills`) confirmed; same `SKILL.md` format plus an optional
  `metadata.hermes` block. The built-in install-dir skill root differs per Hermes build and
  is not auto-discovered — pass `--root` for it, and if `$HERMES_HOME` is non-default, pass
  `--root $HERMES_HOME/skills`.
