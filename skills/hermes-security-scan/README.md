# 🛡️ hermes-security-scan

Security auditor for [Hermes Agent](https://github.com/NousResearch/hermes-agent) configurations.

Scans your `~/.hermes/` directory for vulnerabilities, misconfigurations, and prompt injection in installed skills.

## Quick Start

```bash
# Run the scan
python3 scripts/hermes_security_scan.py

# JSON output
python3 scripts/hermes_security_scan.py --format json

# Verbose (show INFO-level findings)
python3 scripts/hermes_security_scan.py -v
```

## What It Scans

| Category | Weight | Examples |
|----------|--------|---------|
| **Secrets** (30%) | .env permissions, hardcoded keys in config.yaml, secrets in memory/cron files | `sk-ant-*`, `ghp_*`, database URLs |
| **Config** (25%) | Approval mode, command allowlist, agent limits | `mode: yolo`, `rm -rf` in allowlist |
| **MCP Servers** (20%) | Supply chain, remote URLs, auto-approve | `npx -y`, shell metacharacters |
| **Skills** (15%) | Prompt injection (10 patterns), Unicode tricks | `ignore previous instructions`, zero-width chars |
| **Privacy** (10%) | Redaction, blocklist, private URL access | `redact_secrets: false` |

## Sample Output

```
  🛡️  Hermes Security Scan

  Grade: B (85/100)

  Score Breakdown
  Secrets        ████████████████████ 100
  Config         ████████████████████ 100
  MCP Servers    ████████████████████ 100
  Skills         ██████████████░░░░░░ 70
  Privacy        ███████████████████░ 98

  ● CRITICAL  Skill 'skills/bad-skill/SKILL.md': Ignore previous instructions
    ~/.hermes/skills/bad-skill/SKILL.md:13
    Fix: Review this skill file manually for malicious intent.

  ○ LOW       Website blocklist disabled
    ~/.hermes/config.yaml
    Fix: Enable security.website_blocklist if you want to restrict web access.

  Summary
  Files scanned: 245
  Findings: 3 total — 1 critical, 1 low, 1 info
```

## Hermes Skill Installation

### Local install

```bash
# Copy to Hermes skills directory
mkdir -p ~/.hermes/skills/hermes-security-scan/scripts
cp SKILL.md ~/.hermes/skills/hermes-security-scan/
cp scripts/hermes_security_scan.py ~/.hermes/skills/hermes-security-scan/scripts/
cp scripts/scan.py ~/.hermes/skills/hermes-security-scan/scripts/
```

### GitHub / Skills Hub friendly layout

This repo is structured as a standalone Hermes skill directory, so it can be installed directly from GitHub or packaged as a `.skill` file.

```bash
# Example packaging command
python3 -m scripts.package_skill ~/.hermes/skills/hermes-security-scan ~/Downloads
```

Then ask your Hermes agent: *"Run a security scan"*

## Severity & Grading

| Severity | Points | Action |
|----------|--------|--------|
| CRITICAL | -25 | Fix immediately |
| HIGH | -15 | Fix soon |
| MEDIUM | -5 | Review |
| LOW | -2 | Informational |
| INFO | 0 | Noting |

| Grade | Score | Meaning |
|-------|-------|---------|
| A | 90+ | Excellent |
| B | 75-89 | Good |
| C | 60-74 | Acceptable |
| D | 40-59 | Poor |
| F | <40 | Failing |

## Design Decisions

- **Code-block aware**: Patterns inside fenced blocks (including indented markdown fences) are ignored for code-block-aware rules — prevents false positives from code examples
- **Reference file skip**: `references/`, `templates/`, `assets/` subdirectories in skills are skipped — they're documentation, not active instructions
- **Conservative instruction heuristics**: Workflow advice like "run X first" or "run two sessions in parallel" should not be flagged unless it also pressures the agent to act without asking/confirmation
- **Conservative exfiltration heuristics**: `curl -X POST` examples are only flagged when they also look like external secret exfiltration, not ordinary API usage examples
- **.env is expected**: Secrets in `.env` are INFO-level (that's where they belong) — only file permissions matter
- **stdlib only**: No dependencies beyond Python 3.8 stdlib (PyYAML optional for better config parsing)

## License

MIT
