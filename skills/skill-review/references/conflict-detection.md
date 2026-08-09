# Conflict Detection (vs installed skills)

Will installing the candidate break triggering of, or be confused with, an already-installed
skill? Inputs: the candidate's `{name, description, declared_allowed_tools}` and the
`catalog.json` of installed skills `{name, description}` only — **never** other skills'
internal files (unnecessary, and a scope/privacy concern).

## Checks

1. **Name collision (deterministic).** Normalize both names: lowercase, strip
   hyphens/underscores/spaces. Exact normalized match → `high` (`name_collision`): install
   will shadow/overwrite an installed skill. Near-match (Levenshtein ≤2, or one is a substring
   of the other) → `medium` confusion risk.

2. **Trigger-phrase overlap (deterministic + LLM).** Extract each description's *trigger
   surface*: the "use when…/触发" clauses, verb+object pairs ("create dashboard", "send email"),
   named file types/extensions, URL/route patterns, product nouns. Compute lexical overlap
   (shared n-grams / Jaccard on trigger tokens). High overlap → candidate for collision.
   **Adjudicate with probe queries:** generate a handful of queries the candidate intends to
   capture; if an installed skill would plausibly win or tie on the candidate's *own* intended
   queries, that is a real `trigger_collision`.

3. **Route / pattern overlap (deterministic).** Two skills both claiming the same concrete
   patterns (`/docx/`, `*.xlsx`, a `bitable` token, a CLI name) → `route_overlap`; the host
   cannot disambiguate by pattern. (Real precedent in this environment: `lark-whiteboard` vs
   `lark-whiteboard-cli`; the carefully carved boundaries among the many `lark-*` doc skills.)

4. **Functional overlap vs contradiction (LLM).**
   - **Overlap** (same job, ambiguous trigger) → `functional_overlap`, WARN. Recommend
     tightening one description's scope.
   - **Contradiction** (same trigger, opposite behavior — e.g. one always uploads, one always
     keeps local) → `functional_contradiction`, higher severity: wrong-skill activation yields
     actively wrong results.

5. **Greedy description (LLM).** So broad it would steal triggers from many narrow installed
   skills → `greedy_description`, even without a single named victim.

## Conflict finding object (goes inside `findings[]` for the conflict reviewer)

```json
{
  "id": "CF-001",
  "dimension": "skill_conflict",
  "conflict_type": "trigger_collision",
  "severity": "medium",
  "confidence": "medium",
  "file": "SKILL.md",
  "locator": "frontmatter description",
  "conflicts_with": "lark-whiteboard",
  "evidence_summary": "Both trigger on whiteboard/architecture-diagram intents; probe query 'draw an architecture diagram' routes ambiguously.",
  "effect": "Wrong-skill activation; candidate may suppress lark-whiteboard or vice versa.",
  "recommended_action": "caution",
  "forces_block": false
}
```

`conflict_type` ∈ `name_collision | trigger_collision | route_overlap |
functional_overlap | functional_contradiction | greedy_description`.

## Remediation language

Prefer suggesting a fix over rejecting: point the user at skill-creator's boundary-clause
pattern ("not responsible for X — use Y instead") to scope the candidate or the colliding
skill. A `name_collision` or trigger-stealing description forces at least WARN even when the
candidate is otherwise clean, because it breaks the existing install.
