# Acknowledgements

## Anthropic `skill-creator` (Apache License 2.0)

skill-review was **authored using** [Anthropic's `skill-creator`](https://github.com/anthropics/skills/tree/main/skills/skill-creator)
— part of the [`anthropics/skills`](https://github.com/anthropics/skills) repository, which is
licensed under the **Apache License, Version 2.0**.

`skill-creator` was used as the **authoring methodology and tooling** to scaffold, validate and
package this skill, and skill-review follows the **Claude Agent Skills** format/specification
(e.g. the `SKILL.md` frontmatter conventions: kebab-case `name` ≤ 64 chars, `description`
≤ 1024 chars, `references/` + `scripts/` + `assets/` layout).

### Scope of borrowing

- skill-review's scripts (`enumerate_skill.py`, `prescan.py`, `frontmatter.py`,
  `aggregate_findings.py`, `package_dist.py`, `sandbox_run.py`, etc.) are an **independent
  implementation** written for this project. They follow the same *skill-format specification*
  as `skill-creator` (which is a functional spec, not protected expression), but are **not a
  verbatim copy** of `skill-creator`'s source code.
- No source files from `anthropics/skills` are bundled in or redistributed by skill-review.

Because no Apache-2.0-licensed source is copied verbatim, skill-review's own original code is
released under the [MIT License](LICENSE). This acknowledgement is provided for accuracy and out
of respect for the upstream project; per Apache-2.0 §6 (Trademarks), it describes the origin of
the work and does **not** imply any endorsement.

### Independence / non-endorsement

**skill-review is an independent, community project. It is not an official Anthropic product,
and it is not affiliated with, sponsored by, or endorsed by Anthropic, PBC.** "Claude" and
"Anthropic" are trademarks of Anthropic, PBC, referenced here only to accurately describe the
tooling and format skill-review builds upon.

### Reference

- Upstream: https://github.com/anthropics/skills (Apache-2.0)
- skill-creator: https://github.com/anthropics/skills/tree/main/skills/skill-creator
