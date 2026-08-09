# Changelog

All notable changes to **skill-review** are documented here.
This project adheres to [Semantic Versioning](https://semver.org/).

## [1.0.0] — 2026-06-14

First complete, validated release.

### Added
- **Orchestration** (`SKILL.md`): two modes — pre-install gate (single candidate) and
  on-demand audit (installed-skill portfolio); bilingual (EN/中文) triggering; runtime-agnostic.
- **Deterministic layer** (12 stdlib-only scripts): `enumerate_skill`, `prescan` (bilingual
  signature scan), `frontmatter`, `discover_skills` (cross-runtime), `aggregate_findings`,
  `gen_dashboard` (static HTML), `selftest`, `package_dist`.
- **Isolated multi-perspective review**: 4 reviewer roles (red-team, exfil/privacy, injection,
  conflict) + synthesizer, each returning structured JSON; the orchestrator never reads raw text.
- **Hardened isolation envelope**: `prepare_bundle` (neutralizes invisible/bidi unicode →
  visible sentinels) as enforced input; `validate_findings` (schema gate rejecting non-schema /
  smuggled output) as enforced output.
- **Dynamic sandbox** (`sandbox_run` + `assets/sandbox/Dockerfile`): Docker honeytokens +
  `--trace` strace, catching secret `openat()` and `connect()` under `--network none`.
- **7 threat dimensions**, severity × confidence model, PASS/WARN/BLOCK gate with forced-block
  red lines, four-gate false-positive disambiguation, and enforcement guardrails (quarantine,
  never auto-install, never execute host-side audited code).
- **Cross-runtime profiles**: Claude Code, openclaw, Codex, Hermes, generic.
- **HTML risk dashboard**, settings.json install-reminder hook, provenance dimension,
  `references/limitations.md` (honest scope).

### Security
- Fixed a stored-XSS / `</script>` breakout in the HTML dashboard (a malicious skill's finding
  text could run JS in the auditor's browser).
- Crash-guarded `aggregate_findings` against malformed reviewer severity.
- Broadened the output gate and the invisible-unicode signature set.

### Validated
- Internal self-test: 10/10 recall, 3/3 precision.
- External corpus (documented real-world attacks): 7/7 after fixing 2 real gaps
  (agent-instruction-file poisoning; npm lifecycle hooks).
- Live: injection reviewer reports rather than obeys; Docker honeytoken caught; dogfood
  self-audit PASS with zero false positives; real `wiki-tree` audit → WARN.
