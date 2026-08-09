# Limitations & Honest Scope

skill-review is a **high-quality first-pass filter that produces evidence**, not an absolute
safety guarantee. State these limits in any report whose verdict is PASS, and never let a
clean result read as "proven safe."

## What it does NOT guarantee

- **Not complete recall.** "Perfect review" is the design *direction*, not a claim. The
  deterministic prescan only catches **known signatures** (hand-written, certainly
  incomplete — bugs/gaps have already been found and fixed during testing). The LLM reviewers
  add judgment but can miss a sufficiently novel or well-obfuscated attack. A PASS means
  "nothing the current methods caught," not "guaranteed benign."
- **Self-test numbers are directional, not external validation.** `selftest.py`'s
  recall/precision is measured on **fixtures authored alongside the signatures** — useful for
  catching regressions, but not evidence of real-world detection rate (the test corpus and
  the detector share an author). Concretely: an **external corpus** reconstructed from public
  2025-2026 attack research (Unicode-Tag smuggling, GlassWorm zero-width steganography,
  CLAUDE.md/.cursorrules poisoning, npm preinstall auto-exec, MCP tool-poisoning) initially
  scored **71% (5/7)** while the self-authored fixtures scored 100% — exactly the gap this
  warning predicts. The two misses (agent-instruction-file poisoning; npm lifecycle hooks)
  were then fixed. But that corpus is still small and curated; recall on genuinely novel or
  well-obfuscated attacks remains bounded. Treat percentages as a regression signal, not a
  safety rating.
- **Comparable tools do more.** Dedicated scanners (e.g. cisco-ai-defense/skill-scanner) add
  `.pyc` bytecode integrity, AST/dataflow taint analysis, and VirusTotal hash lookups that
  skill-review does not. skill-review's edge is the isolated multi-perspective review +
  hardened envelope + dynamic honeytokens, not signature breadth.

## Isolation: hardened envelope, not OS-hard isolation

The reviewer's **input** is neutralized (`prepare_bundle.py` — invisible unicode defanged,
content capped/wrapped) and its **output** is schema-enforced (`validate_findings.py` —
rejects non-schema JSON / smuggled markers). The orchestrator and synthesizer consume only
structured JSON. This is materially stronger than prompt-only isolation. But:

- The LLM's **reasoning** cannot be OS-sandboxed — reading-and-understanding text is the
  attack surface. A maximally sophisticated injection could still influence a reviewer's
  judgment; the envelope limits *what it can act on and smuggle out*, not whether it can be
  persuaded.
- Isolation is only as strong as the runtime allows. If the host cannot withhold raw-file
  tools from a reviewer subagent, "consume only the bundle" is an instruction, not a hard
  wall. **Sequential-fallback mode** (no subagents) is weaker still — untrusted text enters a
  single context; reports MUST carry the `⚠ strict isolation not enforced` banner.

## Dynamic sandbox: partial, opt-in

- Runs only `.py`/`.sh` inside Docker. PowerShell/`.ps1`, compiled binaries, and Node are
  **not** dynamically executed — they rely on static analysis only.
- With `--network none`, real egress is blocked, so detection is via **honeytoken reads**
  (canary in stdout/written files) and **attempted destinations** in output/`--trace`
  syscalls — not full in-flight payload capture. A script that reads a secret and posts it
  without printing/staging may leave only a blocked-connect trace.
- Requires Docker running; otherwise the verdict is **static-only** (reported as such).

## Other honest caveats

- **Cost/scale.** A deep multi-role audit of one substantial skill can cost hundreds of
  thousands of tokens; a large Mode B portfolio is expensive. The no-scripts fast-path helps,
  but deep audits are heavy by design.
- **Conflict detection is heuristic.** Trigger-collision judgment is LLM-subjective and
  depends on the installed-skills catalog being complete.
- **Provenance is advisory.** No script computes signatures/hashes yet; the dimension relies
  on discovery context + reviewer judgment.
- **Auditing skill-review itself (self-reference):** its own `tests/fixtures/` and the
  signature strings in `scripts/prescan.py`/`threat-taxonomy.md` look "dangerous" but are the
  auditor's declared test corpus and pattern definitions, not active payloads. A live
  dogfood self-audit confirmed the reviewers clear these correctly via the necessity +
  disclosure gates (verdict PASS, zero false positives) — no special-case exclusion is hard-
  coded, the four-gate handling is what does it. `package_dist.py --no-fixtures` omits the
  malicious fixtures from a distributable zip for AV-sensitive environments.

## Use it as

A strong, evidence-producing **first filter and triage aid** that catches the obvious-to-
moderately-clever malicious skill and surfaces dual-use risks for a human decision — paired
with human judgment for anything high-stakes, not as a sole gate that makes installation
"safe."
