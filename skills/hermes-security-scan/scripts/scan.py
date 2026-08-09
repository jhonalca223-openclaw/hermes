#!/usr/bin/env python3
"""
Hermes Security Scanner — comprehensive audit of ~/.hermes/ installations.
Pure Python, no external dependencies. Checks 20+ risk categories.

Usage:
    python scan.py                    # Terminal colored output
    python scan.py --format json      # JSON output
    python scan.py --fix              # Auto-fix safe issues (permissions)
    python scan.py --hermes-home /path # Scan specific installation
"""

import argparse
import json
import os
import re
import stat
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


# ─── Data Structures ────────────────────────────────────────────

CRITICAL, HIGH, MEDIUM, INFO = "CRITICAL", "HIGH", "MEDIUM", "INFO"
SEVERITY_WEIGHT = {CRITICAL: 20, HIGH: 10, MEDIUM: 5, INFO: 1}
SEVERITY_EMOJI = {CRITICAL: "🔴", HIGH: "🟠", MEDIUM: "🟡", INFO: "🔵"}


@dataclass
class Finding:
    severity: str
    category: str
    title: str
    detail: str
    fix: str = ""
    auto_fixable: bool = False

    def penalty(self) -> int:
        return SEVERITY_WEIGHT.get(self.severity, 0)


@dataclass
class ScanResult:
    findings: list = field(default_factory=list)
    hermes_home: str = ""
    checks_run: int = 0

    def grade(self) -> tuple:
        total_penalty = sum(f.penalty() for f in self.findings)
        score = max(0, 100 - total_penalty)
        if score >= 90:
            return "A", score
        elif score >= 75:
            return "B", score
        elif score >= 60:
            return "C", score
        elif score >= 40:
            return "D", score
        else:
            return "F", score


# ─── Helpers ────────────────────────────────────────────────────

def _perm_octal(path: Path) -> Optional[str]:
    try:
        return oct(path.stat().st_mode & 0o777)
    except (OSError, ValueError):
        return None


def _is_world_readable(path: Path) -> bool:
    try:
        return bool(path.stat().st_mode & stat.S_IROTH)
    except OSError:
        return False


def _read_text(path: Path) -> Optional[str]:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _parse_yaml_simple(text: str) -> dict:
    """Minimal YAML parser for flat/simple nested configs. No dependency needed."""
    result = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" in stripped:
            key, _, val = stripped.partition(":")
            val = val.strip().strip("'\"")
            if val.lower() == "true":
                val = True
            elif val.lower() == "false":
                val = False
            result[key.strip()] = val
    return result


def _parse_env(text: str) -> dict:
    result = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, val = line.partition("=")
            result[key.strip()] = val.strip().strip("'\"")
    return result


def _load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


# ─── Check Functions ────────────────────────────────────────────

def check_file_permissions(home: Path, result: ScanResult, fix: bool):
    """Check permissions on sensitive files."""
    checks = [
        (home / ".env", "0o600", CRITICAL, "API keys and bot tokens in plaintext"),
        (home / "config.yaml", "0o600", HIGH, "May contain inline API keys"),
        (home / "state.db", "0o600", HIGH, "Session history with conversation data"),
        (home / "state.db-wal", "0o600", MEDIUM, "Write-ahead log for state.db"),
        (home / "state.db-shm", "0o600", MEDIUM, "Shared memory for state.db"),
    ]
    dir_checks = [
        (home / "memories", "0o700", HIGH, "Personal memory data"),
        (home / "cron", "0o700", MEDIUM, "Cron job definitions"),
        (home / "skills", "0o700", MEDIUM, "Skill scripts — executable code"),
        (home / "audio_cache", "0o700", INFO, "Voice/audio recordings"),
    ]

    for path, expected, severity, reason in checks:
        if not path.exists():
            continue
        result.checks_run += 1
        actual = _perm_octal(path)
        if actual and actual != expected:
            finding = Finding(
                severity=severity,
                category="permissions",
                title=f"{path.name} is {actual} (should be {expected})",
                detail=f"{reason}. Current: {actual}, expected: {expected}",
                fix=f"chmod 600 {path}",
                auto_fixable=True,
            )
            result.findings.append(finding)
            if fix:
                os.chmod(path, 0o600)

    for path, expected, severity, reason in dir_checks:
        if not path.exists():
            continue
        result.checks_run += 1
        if _is_world_readable(path):
            finding = Finding(
                severity=severity,
                category="permissions",
                title=f"{path.name}/ is world-readable",
                detail=f"{reason}. Directory should be {expected}",
                fix=f"chmod 700 {path}",
                auto_fixable=True,
            )
            result.findings.append(finding)
            if fix:
                os.chmod(path, 0o700)


def check_env_file(home: Path, result: ScanResult):
    """Check .env for dangerous settings."""
    env_path = home / ".env"
    text = _read_text(env_path)
    if not text:
        return

    env = _parse_env(text)

    # CRITICAL: SUDO_PASSWORD stored
    result.checks_run += 1
    if env.get("SUDO_PASSWORD"):
        result.findings.append(Finding(
            severity=CRITICAL,
            category="secrets",
            title="SUDO_PASSWORD is set in .env",
            detail="Root/sudo password stored in plaintext file",
            fix="Remove SUDO_PASSWORD from .env. Use passwordless sudo or manual entry.",
        ))

    # CRITICAL: GATEWAY_ALLOW_ALL_USERS
    result.checks_run += 1
    val = env.get("GATEWAY_ALLOW_ALL_USERS", "").lower()
    if val in ("true", "1", "yes"):
        result.findings.append(Finding(
            severity=CRITICAL,
            category="access-control",
            title="GATEWAY_ALLOW_ALL_USERS is enabled",
            detail="Anyone can interact with your agent on all gateway platforms",
            fix="Set GATEWAY_ALLOW_ALL_USERS=false and configure *_ALLOWED_USERS per platform.",
        ))

    # HIGH: Platform tokens without allowed users
    platforms = {
        "TELEGRAM": ("TELEGRAM_BOT_TOKEN", "TELEGRAM_ALLOWED_USERS"),
        "DISCORD": ("DISCORD_BOT_TOKEN", "DISCORD_ALLOWED_USERS"),
        "SLACK": ("SLACK_BOT_TOKEN", "SLACK_ALLOWED_USERS"),
        "MATRIX": ("MATRIX_ACCESS_TOKEN", "MATRIX_ALLOWED_USERS"),
        "MATTERMOST": ("MATTERMOST_TOKEN", "MATTERMOST_ALLOWED_USERS"),
    }
    for name, (token_key, users_key) in platforms.items():
        result.checks_run += 1
        if env.get(token_key) and not env.get(users_key):
            result.findings.append(Finding(
                severity=HIGH,
                category="access-control",
                title=f"{name} bot token set but {users_key} is empty",
                detail=f"No access control on {name} gateway — anyone who finds the bot can use it",
                fix=f"Set {users_key} to comma-separated user IDs in .env",
            ))

    # HIGH: API server without auth key
    result.checks_run += 1
    if env.get("API_SERVER_ENABLED", "").lower() in ("true", "1"):
        if not env.get("API_SERVER_KEY"):
            result.findings.append(Finding(
                severity=HIGH,
                category="access-control",
                title="API server enabled without API_SERVER_KEY",
                detail="Anyone with network access can send commands to your agent",
                fix="Set API_SERVER_KEY to a strong random string in .env",
            ))

    # MEDIUM: DISCORD_ALLOW_BOTS
    result.checks_run += 1
    if env.get("DISCORD_ALLOW_BOTS"):
        result.findings.append(Finding(
            severity=MEDIUM,
            category="access-control",
            title="DISCORD_ALLOW_BOTS is set",
            detail=f"Value: {env['DISCORD_ALLOW_BOTS']}. Allows bot-to-bot interaction (chain attack vector)",
            fix="Remove DISCORD_ALLOW_BOTS unless bot interaction is intentionally needed.",
        ))


def check_config_yaml(home: Path, result: ScanResult):
    """Check config.yaml for secrets and risky settings."""
    config_path = home / "config.yaml"
    text = _read_text(config_path)
    if not text:
        return

    # Check for inline API keys/secrets in YAML
    result.checks_run += 1
    secret_patterns = [
        (r'api_key:\s*["\']?[a-zA-Z0-9_\-]{20,}', "API key found inline in config.yaml"),
        (r'(sk-|ghp_|gho_|xox[bpsa]-|AIza)[a-zA-Z0-9_\-]{10,}', "Known API key prefix found in config.yaml"),
    ]
    for pattern, msg in secret_patterns:
        matches = re.findall(pattern, text)
        if matches:
            result.findings.append(Finding(
                severity=CRITICAL,
                category="secrets",
                title=msg,
                detail=f"Found {len(matches)} potential secret(s). Secrets should be in .env, not config.yaml",
                fix="Move API keys to .env and reference them via environment variables.",
            ))

    # Check approval mode
    result.checks_run += 1
    approvals_block = re.search(r'(?ms)^approvals:\s*\n(?P<body>(?:^[ \t].*\n?)*)', text)
    approval_body = approvals_block.group('body') if approvals_block else ''
    if re.search(r'(?m)^[ \t]+mode:\s*["\']?auto\b', approval_body):
        result.findings.append(Finding(
            severity=HIGH,
            category="config",
            title="Approval mode is 'auto' (no human oversight)",
            detail="Dangerous terminal commands are auto-approved by LLM without human confirmation",
            fix="Set approvals.mode to 'manual' in config.yaml for human-in-the-loop.",
        ))

    # Check command_allowlist
    result.checks_run += 1
    allowlist_match = re.findall(r'command_allowlist:.*?\n((?:\s+-\s+.+\n)*)', text)
    if allowlist_match:
        entries = re.findall(r'-\s+(.+)', allowlist_match[0])
        broad_patterns = [e for e in entries if any(w in e.lower() for w in
                          ["*", "rm", "sudo", "chmod", "kill", "dd", "mkfs"])]
        if broad_patterns:
            result.findings.append(Finding(
                severity=HIGH,
                category="config",
                title=f"Dangerous commands in allowlist: {broad_patterns}",
                detail="These commands bypass safety checks permanently",
                fix="Review and remove overly broad patterns from command_allowlist in config.yaml.",
            ))

    # Check tirith settings
    result.checks_run += 1
    if re.search(r'tirith_enabled:\s*false', text):
        result.findings.append(Finding(
            severity=MEDIUM,
            category="config",
            title="Tirith security scanner is disabled",
            detail="Pre-execution content scanning (homograph URLs, pipe-to-shell, etc.) is off",
            fix="Set security.tirith_enabled: true in config.yaml.",
        ))

    result.checks_run += 1
    if re.search(r'tirith_fail_open:\s*true', text):
        result.findings.append(Finding(
            severity=MEDIUM,
            category="config",
            title="Tirith fail-open is enabled",
            detail="If the security scanner crashes, commands are allowed through instead of blocked",
            fix="Set security.tirith_fail_open: false in config.yaml.",
        ))

    # Check secret redaction
    result.checks_run += 1
    if re.search(r'redact_secrets:\s*false', text):
        result.findings.append(Finding(
            severity=MEDIUM,
            category="config",
            title="Secret redaction is disabled",
            detail="API keys and tokens may appear in agent logs and session history",
            fix="Set security.redact_secrets: true in config.yaml.",
        ))

    # Check browser private URLs
    result.checks_run += 1
    if re.search(r'allow_private_urls:\s*true', text):
        result.findings.append(Finding(
            severity=MEDIUM,
            category="config",
            title="Browser allows private/internal URLs",
            detail="Agent can access LAN services, internal APIs, and localhost",
            fix="Set browser.allow_private_urls: false unless specifically needed.",
        ))

    # Check MCP servers for inline secrets
    result.checks_run += 1
    mcp_section = re.findall(r'mcp_servers:.*?(?=\n\w|\Z)', text, re.DOTALL)
    if mcp_section:
        mcp_text = mcp_section[0]
        secret_in_mcp = re.findall(r'(sk-|ghp_|xox[bpsa]-|AIza|key|token|secret)\S{10,}', mcp_text, re.IGNORECASE)
        if secret_in_mcp:
            result.findings.append(Finding(
                severity=MEDIUM,
                category="mcp",
                title="Potential secrets in MCP server configuration",
                detail=f"Found {len(secret_in_mcp)} possible secret(s) inline in mcp_servers config",
                fix="Use environment variable references instead of inline secrets in MCP configs.",
            ))


def check_migration_backups(home: Path, result: ScanResult):
    """Check for leftover migration backups containing secrets."""
    migration_dir = home / "migration"
    result.checks_run += 1
    if not migration_dir.exists():
        return

    sensitive_files = list(migration_dir.rglob("*.env*")) + list(migration_dir.rglob("*config*"))
    if sensitive_files:
        names = [f.name for f in sensitive_files[:5]]
        result.findings.append(Finding(
            severity=HIGH,
            category="secrets",
            title=f"Migration backup contains sensitive files: {names}",
            detail=f"Found {len(sensitive_files)} potentially sensitive file(s) in {migration_dir}",
            fix=f"Review and delete: rm -rf {migration_dir}",
        ))


def check_cron_jobs(home: Path, result: ScanResult):
    """Audit cron jobs for exfiltration patterns."""
    jobs_file = home / "cron" / "jobs.json"
    jobs = _load_json(jobs_file)
    if not jobs:
        return

    if isinstance(jobs, dict):
        jobs = jobs.get("jobs", [])

    exfil_patterns = [
        r'curl\s+.*\.(env|yaml|json)',
        r'wget\s+.*\.(env|yaml|json)',
        r'cat\s+.*\.(env|config)',
        r'send.*\.env',
        r'upload.*secret',
        r'base64.*\.env',
    ]

    for job in jobs:
        if not isinstance(job, dict):
            continue
        result.checks_run += 1
        prompt = job.get("prompt", "")
        job_name = job.get("name", job.get("id", "unnamed"))

        for pattern in exfil_patterns:
            if re.search(pattern, prompt, re.IGNORECASE):
                result.findings.append(Finding(
                    severity=HIGH,
                    category="cron",
                    title=f"Cron job '{job_name}' has potential exfiltration pattern",
                    detail=f"Pattern matched: {pattern}",
                    fix=f"Review cron job prompt and remove suspicious commands.",
                ))
                break

        # Check if job delivers to unexpected targets
        deliver = job.get("deliver", "")
        if deliver and deliver not in ("local", "origin"):
            result.findings.append(Finding(
                severity=INFO,
                category="cron",
                title=f"Cron job '{job_name}' delivers to external target: {deliver}",
                detail="Job output is sent to a platform channel",
                fix="Verify this delivery target is intentional.",
            ))


def check_skills(home: Path, result: ScanResult):
    """Audit skills for suspicious scripts."""
    skills_dir = home / "skills"
    if not skills_dir.exists():
        return

    suspicious_patterns = [
        (r'urllib|requests\.get|requests\.post|httpx', "Network call in skill script"),
        (r'os\.environ\[.*(KEY|TOKEN|SECRET|PASSWORD)', "Reading sensitive env vars"),
        (r'subprocess.*curl|subprocess.*wget', "Subprocess network call"),
        (r'eval\(|exec\(', "Dynamic code execution"),
        (r'open\(.*/\.env', "Reading .env file directly"),
        (r'socket\.(connect|bind)', "Raw socket usage"),
    ]

    for script_path in skills_dir.rglob("scripts/*"):
        if not script_path.is_file():
            continue
        if script_path.suffix not in (".py", ".sh", ".bash"):
            continue

        result.checks_run += 1
        content = _read_text(script_path)
        if not content:
            continue

        # Skip self
        if "hermes-security-scan" in str(script_path):
            continue

        skill_name = script_path.relative_to(skills_dir).parts[0] if len(script_path.relative_to(skills_dir).parts) > 1 else "unknown"

        for pattern, msg in suspicious_patterns:
            if re.search(pattern, content):
                result.findings.append(Finding(
                    severity=INFO,
                    category="skills",
                    title=f"Skill '{skill_name}': {msg}",
                    detail=f"File: {script_path.relative_to(home)}",
                    fix="Review the script to ensure it's from a trusted source.",
                ))
                break  # One finding per script

    # Check external skill dirs
    result.checks_run += 1
    config_text = _read_text(home / "config.yaml")
    if config_text and "external_dirs" in config_text:
        ext_match = re.findall(r'external_dirs:.*?\n((?:\s+-\s+.+\n)*)', config_text)
        if ext_match:
            dirs = re.findall(r'-\s+(.+)', ext_match[0])
            if dirs:
                result.findings.append(Finding(
                    severity=MEDIUM,
                    category="skills",
                    title=f"External skill directories configured: {dirs}",
                    detail="Skills loaded from non-standard locations",
                    fix="Verify these directories contain only trusted skills.",
                ))


def check_git_exposure(home: Path, result: ScanResult):
    """Check if .env might be tracked in git."""
    result.checks_run += 1
    # Check if ~/.hermes is inside a git repo
    git_dir = home / ".git"
    if not git_dir.exists():
        return

    gitignore = home / ".gitignore"
    if gitignore.exists():
        content = _read_text(gitignore) or ""
        if ".env" not in content:
            result.findings.append(Finding(
                severity=HIGH,
                category="secrets",
                title=".env not in .gitignore",
                detail="The .env file (containing API keys/tokens) may be committed to git",
                fix=f"echo '.env' >> {gitignore}",
            ))
    else:
        result.findings.append(Finding(
            severity=HIGH,
            category="secrets",
            title="No .gitignore in hermes home (which is a git repo)",
            detail="Secret files may be tracked by git",
            fix=f"echo '.env\\nstate.db*\\naudio_cache/' > {gitignore}",
        ))


# ─── Output Formatting ─────────────────────────────────────────

def format_terminal(result: ScanResult) -> str:
    grade, score = result.grade()
    lines = []

    # Header
    lines.append("")
    lines.append("╔══════════════════════════════════════════════════╗")
    lines.append("║         🛡️  Hermes Security Scan Report          ║")
    lines.append("╚══════════════════════════════════════════════════╝")
    lines.append(f"  Target: {result.hermes_home}")
    lines.append(f"  Checks: {result.checks_run}  |  Findings: {len(result.findings)}")
    lines.append("")

    # Grade
    grade_bar = "█" * (score // 5) + "░" * (20 - score // 5)
    lines.append(f"  Grade: {grade} ({score}/100)  [{grade_bar}]")
    lines.append("")

    if not result.findings:
        lines.append("  ✅ No issues found. Your Hermes installation looks secure!")
        lines.append("")
        return "\n".join(lines)

    # Group by severity
    for sev in [CRITICAL, HIGH, MEDIUM, INFO]:
        findings = [f for f in result.findings if f.severity == sev]
        if not findings:
            continue

        emoji = SEVERITY_EMOJI[sev]
        lines.append(f"  {emoji} {sev} ({len(findings)})")
        lines.append(f"  {'─' * 46}")
        for f in findings:
            lines.append(f"    [{f.category}] {f.title}")
            lines.append(f"      {f.detail}")
            if f.fix:
                lines.append(f"      → Fix: {f.fix}")
            lines.append("")

    # Summary
    auto_fixable = [f for f in result.findings if f.auto_fixable]
    if auto_fixable:
        lines.append(f"  💡 {len(auto_fixable)} issue(s) can be auto-fixed with --fix")
    lines.append("")
    return "\n".join(lines)


def format_json(result: ScanResult) -> str:
    grade, score = result.grade()
    return json.dumps({
        "hermes_home": result.hermes_home,
        "checks_run": result.checks_run,
        "grade": grade,
        "score": score,
        "findings_count": len(result.findings),
        "findings": [asdict(f) for f in result.findings],
    }, indent=2, ensure_ascii=False)


# ─── Main ───────────────────────────────────────────────────────

def run_scan(hermes_home: Optional[str] = None, fix: bool = False) -> ScanResult:
    if hermes_home:
        home = Path(hermes_home)
    else:
        home = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))

    result = ScanResult(hermes_home=str(home))

    if not home.exists():
        result.findings.append(Finding(
            severity=INFO,
            category="config",
            title=f"Hermes home not found: {home}",
            detail="No installation to scan",
        ))
        return result

    # Run all checks
    check_file_permissions(home, result, fix)
    check_env_file(home, result)
    check_config_yaml(home, result)
    check_migration_backups(home, result)
    check_cron_jobs(home, result)
    check_skills(home, result)
    check_git_exposure(home, result)

    # Sort findings by severity
    sev_order = {CRITICAL: 0, HIGH: 1, MEDIUM: 2, INFO: 3}
    result.findings.sort(key=lambda f: sev_order.get(f.severity, 99))

    return result


def main():
    parser = argparse.ArgumentParser(description="Hermes Security Scanner")
    parser.add_argument("--format", choices=["terminal", "json"], default="terminal")
    parser.add_argument("--fix", action="store_true", help="Auto-fix safe issues (permissions)")
    parser.add_argument("--hermes-home", help="Path to Hermes home directory")
    args = parser.parse_args()

    result = run_scan(hermes_home=args.hermes_home, fix=args.fix)

    if args.format == "json":
        print(format_json(result))
    else:
        output = format_terminal(result)
        print(output)
        if args.fix:
            fixed = [f for f in result.findings if f.auto_fixable]
            if fixed:
                print(f"  ✅ Auto-fixed {len(fixed)} permission issue(s). Re-run to verify.\n")

    # Exit code: 0=A/B, 1=C/D/F
    grade, _ = result.grade()
    sys.exit(0 if grade in ("A", "B") else 1)


if __name__ == "__main__":
    main()
