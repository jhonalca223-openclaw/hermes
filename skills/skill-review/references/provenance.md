# Dimension 7 — Provenance / Trust Signals

Out-of-content trust signals: *where did this skill come from, and has it been tampered with
since?* These complement the six content dimensions. Most provenance findings are `info` or a
small trust credit; **a signed-then-modified skill escalates** because tampering breaks the
Principle of Lack of Surprise at the distribution layer.

## What to look at

| Signal | Good (`info`/credit) | Concerning (escalate) |
|---|---|---|
| **Source declared** | git URL + pinned commit SHA, or a known local path | no source, or `ref: main`/floating tag (unpinnable, can change under you) |
| **Marketplace** | inside an official marketplace tree (e.g. `~/.claude/plugins/marketplaces/claude-plugins-official/...`) | unknown origin, sideloaded, or pasted from chat/email |
| **Signature / integrity** | a manifest hash that matches the current content | **present but content changed after signing** → tamper, `high` |
| **Publisher** | a plausible, consistent author identity | author identity contradicts the prose's provenance claims |
| **Modification time vs source** | files match the declared upstream | files newer than/diverging from the claimed pinned commit |

## How to use it

1. **Discovery context.** `discover_skills.py` records which root/marketplace a skill came
   from (`roots_seen`). Inside an official marketplace → mild trust credit. Sideloaded into a
   skills dir with no manifest → note it, audit content normally (provenance never *lowers*
   content scrutiny, it only adds context).
2. **Tamper check.** If the skill (or its plugin) ships a manifest/lock with a content hash,
   recompute over `SKILL.md` + scripts + templates and compare. Mismatch → `provenance`/`high`
   "content modified after signing".
3. **Pinning.** A skill that fetches or depends on a floating remote ref (`@main`, unpinned
   `pip`/`npm` URL) can silently change behavior on update → `provenance`/`medium`, and it
   pairs naturally with a `dangerous_command` second-stage-fetch finding.

## Boundaries

Provenance is **advisory context**, not a substitute for content review. A skill from a
trusted marketplace still gets the full 6-dimension audit; a skill with no provenance is not
auto-BLOCKed for that reason alone. Provenance can raise WARN/BLOCK only via the tamper and
unpinned-remote cases above, where it indicates the content you reviewed may not be the
content that runs.
