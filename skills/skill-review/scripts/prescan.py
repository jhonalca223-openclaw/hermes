#!/usr/bin/env python3
"""
prescan.py - Deterministic signature scan of a skill (signals, NOT verdicts).

Greps every text file for the patterns in references/threat-taxonomy.md and emits
prescan.json (signals: file, line, signal_family, pattern_name, dimension_hint) plus
prescan.snippets.json (the raw matched lines, QUARANTINED, keyed by signal id, for the
human report only). High recall by design; the reviewer subagents triage signals into
findings and suppress false positives.

Usage:
    prescan.py <skill_dir> [--out prescan.json] [--snippets prescan.snippets.json]

Pure stdlib. Never executes skill code; reads bytes only.
"""

import argparse
import json
import re
import sys
from pathlib import Path

I = re.IGNORECASE

# (signal_family, dimension_hint, pattern_name, regex)
SIGNATURES = [
    # --- network_egress ---
    ("network_egress", "data_exfiltration", "requests.post/put/get", re.compile(r"\brequests\.(post|put|get|request)\b")),
    ("network_egress", "data_exfiltration", "urllib.urlopen/Request", re.compile(r"\burllib\.request\.(urlopen|Request)\b")),
    ("network_egress", "data_exfiltration", "http.client.HTTPSConnection", re.compile(r"\bHTTP(S)?Connection\b")),
    ("network_egress", "data_exfiltration", "socket.connect", re.compile(r"\bsocket\.(socket|connect)\b")),
    ("network_egress", "data_exfiltration", "httpx/aiohttp", re.compile(r"\b(httpx|aiohttp)\b")),
    ("network_egress", "data_exfiltration", "smtplib", re.compile(r"\bsmtplib\.SMTP\b")),
    ("network_egress", "data_exfiltration", "ftp/scp/paramiko", re.compile(r"\b(ftplib|paramiko|scp)\b")),
    ("network_egress", "data_exfiltration", "curl", re.compile(r"\bcurl\b.*(-d|--data|-F|-T|--upload-file)", I)),
    ("network_egress", "data_exfiltration", "wget-post", re.compile(r"\bwget\b.*--post-file", I)),
    ("network_egress", "data_exfiltration", "netcat", re.compile(r"\b(nc|ncat|netcat)\b\s+-")),
    ("network_egress", "data_exfiltration", "dev-tcp", re.compile(r"/dev/tcp/")),
    ("network_egress", "data_exfiltration", "Invoke-WebRequest/RestMethod", re.compile(r"\b(Invoke-WebRequest|Invoke-RestMethod|iwr|irm)\b", I)),
    ("network_egress", "data_exfiltration", "Net.WebClient.Upload", re.compile(r"WebClient\)?\.?(UploadFile|UploadString|DownloadString)", I)),
    ("network_egress", "data_exfiltration", "fetch/XHR/sendBeacon", re.compile(r"\bfetch\s*\(|\bXMLHttpRequest\b|\bsendBeacon\b|new\s+WebSocket\b|new\s+Image\s*\(")),
    ("network_egress", "data_exfiltration", "axios.post", re.compile(r"\baxios\.(post|put)\b")),

    # --- secret_access ---
    ("secret_access", "data_exfiltration", "ssh-keys", re.compile(r"\.ssh/|id_rsa|id_ed25519|authorized_keys")),
    ("secret_access", "data_exfiltration", "aws-creds", re.compile(r"\.aws\b|aws[/\\]credentials")),
    ("secret_access", "data_exfiltration", "cloud-config", re.compile(r"\.config/gcloud|\.kube/config|\.docker/config\.json")),
    ("secret_access", "data_exfiltration", "dotenv", re.compile(r"(^|[^.\w])\.env(\b|['\"/])")),
    ("secret_access", "data_exfiltration", "netrc/npmrc/pypirc", re.compile(r"\.netrc|\.npmrc|\.pypirc")),
    ("secret_access", "data_exfiltration", "browser-creds", re.compile(r"Login Data|Cookies|key4\.db|logins\.json", I)),
    ("secret_access", "data_exfiltration", "shell-history", re.compile(r"\.bash_history|\.zsh_history|\.python_history")),
    ("secret_access", "data_exfiltration", "agent-config", re.compile(r"\.claude(\.json|/)|\.agents/|\.codex/")),
    ("secret_access", "data_exfiltration", "env-dump", re.compile(r"os\.environ\b(?!\.get)|Get-ChildItem\s+Env:|printenv", I)),
    ("secret_access", "unauthorized_access", "system-cred-files", re.compile(r"/etc/shadow|/etc/passwd|reg\s+save\s+HKLM\\SAM", I)),

    # --- credential_literal ---
    ("credential_literal", "unauthorized_access", "aws-akia", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("credential_literal", "unauthorized_access", "github-token", re.compile(r"\b(ghp|gho|github_pat)_[A-Za-z0-9_]{20,}\b")),
    ("credential_literal", "unauthorized_access", "slack-token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("credential_literal", "unauthorized_access", "llm-key", re.compile(r"\bsk-(ant-)?[A-Za-z0-9_-]{20,}\b")),
    ("credential_literal", "unauthorized_access", "google-key", re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b")),
    ("credential_literal", "unauthorized_access", "private-key-block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("credential_literal", "unauthorized_access", "basic-auth-url", re.compile(r"https?://[^/\s:@]+:[^/\s@]+@")),

    # --- suspicious_destination ---
    ("suspicious_destination", "data_exfiltration", "webhook-capture", re.compile(r"webhook\.site|requestbin|pipedream|ngrok\.io|trycloudflare\.com", I)),
    ("suspicious_destination", "data_exfiltration", "paste-site", re.compile(r"pastebin\.com|hastebin|transfer\.sh|0x0\.st|file\.io", I)),
    ("suspicious_destination", "data_exfiltration", "chat-webhook", re.compile(r"discord\.com/api/webhooks|api\.telegram\.org/bot|hooks\.slack\.com", I)),
    ("suspicious_destination", "data_exfiltration", "url-shortener", re.compile(r"\b(bit\.ly|t\.co|tinyurl\.com)/", I)),
    ("suspicious_destination", "unauthorized_access", "cloud-metadata-ssrf", re.compile(r"169\.254\.169\.254|metadata\.google\.internal|100\.100\.100\.200")),
    ("suspicious_destination", "data_exfiltration", "raw-ip-url", re.compile(r"https?://\d{1,3}(\.\d{1,3}){3}")),

    # --- fs_destruction ---
    ("fs_destruction", "dangerous_command", "rm-rf-root-home", re.compile(r"\brm\s+-[rf]{1,2}\s+(/|~|\$HOME|/\*|\.\s*$)")),
    ("fs_destruction", "dangerous_command", "find-delete", re.compile(r"\bfind\s+/\s+.*-delete")),
    ("fs_destruction", "dangerous_command", "dd-disk", re.compile(r"\bdd\b.*of=/dev/(sd|disk|nvme)")),
    ("fs_destruction", "dangerous_command", "mkfs/format", re.compile(r"\bmkfs\b|\bformat\s+[A-Za-z]:", I)),
    ("fs_destruction", "dangerous_command", "shutil.rmtree", re.compile(r"\bshutil\.rmtree\b|\bos\.(remove|unlink)\b")),
    ("fs_destruction", "dangerous_command", "ps-remove-recurse", re.compile(r"Remove-Item\b.*-Recurse\b.*-Force\b", I)),
    ("fs_destruction", "dangerous_command", "del-rd-s", re.compile(r"\b(del\s+/s|rd\s+/s|rmdir\s+/s)", I)),

    # --- privilege_escalation ---
    ("privilege_escalation", "dangerous_command", "sudo/su/pkexec", re.compile(r"\b(sudo|pkexec)\b|\bsu\s+-")),
    ("privilege_escalation", "dangerous_command", "setuid", re.compile(r"chmod\s+(\+s|4[0-7]{3})|setcap\b")),
    ("privilege_escalation", "dangerous_command", "chmod-777-root", re.compile(r"chmod\s+777\s+/|chown\s+root")),
    ("privilege_escalation", "dangerous_command", "runas", re.compile(r"Start-Process\b.*-Verb\s+RunAs", I)),

    # --- security_disable ---
    ("security_disable", "dangerous_command", "disable-defender", re.compile(r"Set-MpPreference\b.*Disable|Add-MpPreference\b.*ExclusionPath|Stop-Service\s+WinDefend", I)),
    ("security_disable", "dangerous_command", "disable-firewall", re.compile(r"netsh\s+advfirewall.*state\s+off|iptables\s+-F|ufw\s+disable", I)),
    ("security_disable", "dangerous_command", "exec-policy-bypass", re.compile(r"Set-ExecutionPolicy\b.*Bypass", I)),
    ("security_disable", "dangerous_command", "disable-sip-gatekeeper", re.compile(r"csrutil\s+disable|spctl\s+--master-disable", I)),
    ("security_disable", "dangerous_command", "edit-sudoers-hosts", re.compile(r"/etc/(sudoers|pam\.d)|>>?\s*/etc/hosts")),

    # --- persistence ---
    ("persistence", "dangerous_command", "cron", re.compile(r"\bcrontab\b|/etc/cron|\bat\s+now")),
    ("persistence", "dangerous_command", "scheduled-task", re.compile(r"schtasks\s+/create|Register-ScheduledTask", I)),
    ("persistence", "dangerous_command", "rc-files-append", re.compile(r">>\s*~?/?\.(bashrc|zshrc|profile|bash_profile)")),
    ("persistence", "dangerous_command", "launchagent/systemd", re.compile(r"LaunchAgents/.*\.plist|systemctl\s+enable", I)),
    ("persistence", "dangerous_command", "run-key/startup", re.compile(r"\\Run\\|shell:startup|RunOnce", I)),
    ("persistence", "dangerous_command", "authorized-keys-append", re.compile(r">>\s*~?/?\.ssh/authorized_keys")),
    ("persistence", "prompt_injection", "agent-instructions-file", re.compile(r"CLAUDE\.md|\.cursorrules|\.clauderc|AGENTS\.md|GEMINI\.md|copilot-instructions|\.windsurfrules", I)),

    # --- remote_exec ---
    ("remote_exec", "dangerous_command", "curl-pipe-sh", re.compile(r"(curl|wget)\b[^\n|]*\|\s*(bash|sh|python|node)", I)),
    ("remote_exec", "dangerous_command", "bash-process-sub", re.compile(r"(bash|sh)\s+<\(\s*curl|sh\s+-c\s+\"\$\(curl", I)),
    ("remote_exec", "dangerous_command", "iex-downloadstring", re.compile(r"IEX\b|Invoke-Expression\b|\|\s*iex\b", I)),
    ("remote_exec", "dangerous_command", "ps-encodedcommand", re.compile(r"-EncodedCommand\b|-enc\s+[A-Za-z0-9+/=]{20,}|-nop\s+-w\s+hidden", I)),
    ("remote_exec", "dangerous_command", "certutil-bitsadmin-mshta", re.compile(r"certutil\b.*-urlcache|bitsadmin\s+/transfer|mshta\s+http", I)),
    ("remote_exec", "dangerous_command", "pip/npm-url-install", re.compile(r"\bpip\s+install\s+https?://|\bnpm\s+install\s+(git\+|https?://)", I)),
    ("remote_exec", "dangerous_command", "npm-lifecycle-hook", re.compile(r"\"(pre|post)install\"\s*:|\"prepare\"\s*:")),

    # --- subprocess_shell ---
    ("subprocess_shell", "intent_mismatch", "subprocess/os.system", re.compile(r"\b(subprocess\.(run|call|Popen|check_output)|os\.system|os\.popen)\b")),
    ("subprocess_shell", "intent_mismatch", "shell-true", re.compile(r"shell\s*=\s*True")),
    ("subprocess_shell", "intent_mismatch", "child_process", re.compile(r"\bchild_process\b|\bexecSync\b|\bspawnSync\b")),

    # --- obfuscation ---
    ("obfuscation", "intent_mismatch", "base64-decode", re.compile(r"\bb64decode\b|base64\.b64decode|FromBase64String", I)),
    ("obfuscation", "intent_mismatch", "hex-rot-decode", re.compile(r"\bbytes\.fromhex\b|codecs\.decode\([^)]*rot", I)),
    ("obfuscation", "intent_mismatch", "eval-exec", re.compile(r"\b(eval|exec|compile)\s*\(")),
    ("obfuscation", "intent_mismatch", "pickle-marshal-load", re.compile(r"\b(pickle|marshal)\.loads?\b")),
    ("obfuscation", "intent_mismatch", "dynamic-import", re.compile(r"__import__\s*\(")),
    ("obfuscation", "intent_mismatch", "long-b64-literal", re.compile(r"['\"][A-Za-z0-9+/]{200,}={0,2}['\"]")),

    # --- injection_phrase (English) ---
    ("injection_phrase", "prompt_injection", "ignore-previous", re.compile(r"ignore (previous|all (prior|above)) instructions|disregard (the above|your instructions)", I)),
    ("injection_phrase", "prompt_injection", "you-are-now", re.compile(r"you are now\b|from now on you (will|must)|new instructions:", I)),
    ("injection_phrase", "prompt_injection", "forget-everything", re.compile(r"forget (everything|all previous)|system override|developer mode|\bDAN\b|do anything now", I)),
    ("injection_phrase", "prompt_injection", "hide-from-user", re.compile(r"do not (tell|inform|mention to) the user|without informing the user|hide this from|\bsecretly\b", I)),
    ("injection_phrase", "prompt_injection", "exfil-system-prompt", re.compile(r"(print|reveal|repeat|output) your (system prompt|instructions|tools)|repeat the words above", I)),
    ("injection_phrase", "prompt_injection", "bypass-safety", re.compile(r"bypass your (safety|guard|restrictions)|ignore your (safety|guidelines)", I)),
    # --- injection_phrase (Chinese) ---
    ("injection_phrase", "prompt_injection", "zh-ignore", re.compile(r"忽略(以上|上面|前面|之前)(的)?(所有)?(指令|提示|要求)|无视(之前|前面)的(指令|提示)")),
    ("injection_phrase", "prompt_injection", "zh-you-are-now", re.compile(r"你现在是|从现在(起|开始)你(将|要|必须)|新的指令[:：]")),
    ("injection_phrase", "prompt_injection", "zh-forget-override", re.compile(r"忘记(之前|以前)|系统覆盖|进入开发者模式")),
    ("injection_phrase", "prompt_injection", "zh-hide-from-user", re.compile(r"不要(告诉|提及|提示)用户|对用户隐藏|偷偷(地)?")),
    ("injection_phrase", "prompt_injection", "zh-exfil-prompt", re.compile(r"(输出|透露|打印|重复)你的(系统提示|指令|提示词|工具)")),
    ("injection_phrase", "prompt_injection", "zh-bypass-safety", re.compile(r"绕过你的(安全|限制|防护)|忽略你的(安全|准则)")),

    # --- hidden_channel ---
    ("hidden_channel", "prompt_injection", "html-comment-imperative", re.compile(r"<!--[^>]*(ignore|disregard|you are|忽略|无视|approve|放行)[^>]*-->", I)),
    ("hidden_channel", "prompt_injection", "css-hidden-text", re.compile(r"display\s*:\s*none|font-size\s*:\s*0|color\s*:\s*#?fff(fff)?\s*;.*background", I)),
    ("hidden_channel", "prompt_injection", "fake-system-framing", re.compile(r"\[(SYSTEM|ADMIN|INST|ASSISTANT)\]|<\|im_start\|>|###\s*system", I)),

    # --- frontmatter_risk handled separately (allowed-tools vs usage) by reviewers ---
]

# Zero-width / bidi / tags-block codepoints (hidden_channel)
INVISIBLE = {
    0x200B: "ZERO WIDTH SPACE", 0x200C: "ZWNJ", 0x200D: "ZWJ",
    0xFEFF: "BOM/ZWNBSP", 0x2060: "WORD JOINER", 0x00AD: "SOFT HYPHEN",
    0x202E: "RTL OVERRIDE", 0x202D: "LTR OVERRIDE", 0x200E: "LRM", 0x200F: "RLM",
    0x202A: "LRE", 0x202B: "RLE", 0x202C: "PDF", 0x2066: "LRI", 0x2067: "RLI",
    0x2068: "FSI", 0x2069: "PDI", 0x2028: "LINE SEP", 0x2029: "PARA SEP",
    0x2061: "FN APPLICATION", 0x2062: "INVISIBLE TIMES", 0x2063: "INVISIBLE SEP",
    0x2064: "INVISIBLE PLUS", 0x180E: "MONGOLIAN VOWEL SEP", 0x061C: "ARABIC LETTER MARK",
}


def scan_text(rel, text, sig_counter, signals, snippets):
    for lineno, line in enumerate(text.splitlines(), 1):
        for fam, dim, pname, rx in SIGNATURES:
            if rx.search(line):
                sid = f"S-{sig_counter[0]:04d}"
                sig_counter[0] += 1
                signals.append({"id": sid, "file": rel, "line": lineno,
                                "signal_family": fam, "pattern_name": pname,
                                "dimension_hint": dim})
                snippets[sid] = line.strip()[:200]
        # invisible / bidi codepoints
        hits = sorted({cp for cp in (ord(ch) for ch in line) if cp in INVISIBLE})
        if hits:
            sid = f"S-{sig_counter[0]:04d}"
            sig_counter[0] += 1
            names = ", ".join(INVISIBLE[cp] for cp in hits)
            signals.append({"id": sid, "file": rel, "line": lineno,
                            "signal_family": "hidden_channel", "pattern_name": f"invisible-unicode ({names})",
                            "dimension_hint": "prompt_injection"})
            snippets[sid] = f"[invisible codepoints: {names}]"
        # Unicode Tags block U+E0000-E007F
        if any(0xE0000 <= ord(ch) <= 0xE007F for ch in line):
            sid = f"S-{sig_counter[0]:04d}"
            sig_counter[0] += 1
            signals.append({"id": sid, "file": rel, "line": lineno,
                            "signal_family": "hidden_channel", "pattern_name": "unicode-tags-block",
                            "dimension_hint": "prompt_injection"})
            snippets[sid] = "[unicode tags-block codepoints]"


def main() -> int:
    ap = argparse.ArgumentParser(description="Deterministic signature prescan")
    ap.add_argument("skill_dir")
    ap.add_argument("--out", default=None)
    ap.add_argument("--snippets", default=None)
    args = ap.parse_args()

    root = Path(args.skill_dir).resolve()
    if not root.exists():
        print(f"error: {root} not found", file=sys.stderr)
        return 1

    signals = []
    snippets = {}
    sig_counter = [1]
    for path in sorted(root.rglob("*")):
        if path.is_dir():
            continue
        try:
            raw = path.read_bytes()
        except OSError:
            continue
        if b"\x00" in raw[:4096]:
            continue  # binary, skip
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("utf-8", errors="replace")
        rel = str(path.relative_to(root)).replace("\\", "/")
        scan_text(rel, text, sig_counter, signals, snippets)

    family_counts = {}
    for s in signals:
        family_counts[s["signal_family"]] = family_counts.get(s["signal_family"], 0) + 1

    snippets_name = Path(args.snippets).name if args.snippets else "prescan.snippets.json"
    result = {"skill_name": root.name, "signal_count": len(signals),
              "signals": signals, "family_counts": family_counts,
              "snippets_path": snippets_name}

    out = json.dumps(result, indent=2, ensure_ascii=False)
    if args.out:
        Path(args.out).write_text(out, encoding="utf-8")
        print(f"wrote {args.out} ({len(signals)} signals: {family_counts})")
    else:
        print(out)
    if args.snippets:
        Path(args.snippets).write_text(
            json.dumps(snippets, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"wrote {args.snippets} (quarantined raw lines)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
