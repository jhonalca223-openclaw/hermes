#!/usr/bin/env python3
"""
sandbox_run.py - Optional dynamic layer: execute a skill's scripts inside a locked-down
Docker container with planted honeytokens, and report what they touched.

SAFETY MODEL
  - Executes untrusted code ONLY inside Docker, NEVER on the host.
  - Default --network none (no real egress is possible).
  - Non-root, all caps dropped, no-new-privileges, read-only rootfs, memory/cpu/pid limits,
    hard timeout, --rm. A fake HOME is planted with CANARY credentials (honeytokens).
  - Requires explicit --yes to actually run (executing untrusted code is a real action).
    Without --yes it prints the plan and exits.
  - If Docker is unavailable, it degrades: writes dynamic.json with ran=false and a reason.

DETECTION (v1)
  - honeytoken_hits: a canary string appears in stdout/stderr or in any file the script
    wrote, OR (best-effort) the canary credential file was opened. Means the script actually
    reached for the planted secret at runtime.
  - network_attempts: suspicious destinations seen in stdout/stderr (e.g. a ConnectionError
    traceback naming the host the script tried to reach, since egress is blocked).
  Limits are documented in references/windows-sandbox-notes.md.

Usage:
    sandbox_run.py <skill_dir> [--yes] [--image python:3.12-slim] [--timeout 20]
                   [--out dynamic.json] [--script scripts/foo.py ...]
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

DEFAULT_IMAGE = "skill-review-sandbox"   # custom image (strace + requests); falls back below
FALLBACK_IMAGE = "python:3.12-slim"

CANARY = "AKIA" + "CANARY" + uuid.uuid4().hex[:12].upper()
SUSPECT_HOST_HINTS = ["webhook.site", "pastebin", "ngrok", "discord.com/api/webhooks",
                      "api.telegram.org", "hooks.slack.com", "transfer.sh", "requestbin",
                      "0x0.st", "file.io", "trycloudflare"]


def docker_available() -> tuple:
    exe = shutil.which("docker")
    if not exe:
        return False, "docker not found on PATH"
    try:
        r = subprocess.run([exe, "info", "--format", "{{.ServerVersion}}"],
                           capture_output=True, text=True, timeout=20)
        if r.returncode != 0:
            return False, f"docker daemon not running ({r.stderr.strip()[:120]})"
        return True, r.stdout.strip()
    except Exception as e:
        return False, f"docker check failed: {e}"


def plant_honeytokens(home: Path):
    (home / ".aws").mkdir(parents=True, exist_ok=True)
    (home / ".aws" / "credentials").write_text(
        f"[default]\naws_access_key_id = {CANARY}\n"
        f"aws_secret_access_key = wJalrXUtnFEMI/{CANARY}/EXAMPLEKEY\n", encoding="utf-8")
    (home / ".ssh").mkdir(parents=True, exist_ok=True)
    (home / ".ssh" / "id_rsa").write_text(
        f"-----BEGIN OPENSSH PRIVATE KEY-----\n{CANARY}\n-----END OPENSSH PRIVATE KEY-----\n",
        encoding="utf-8")
    (home / ".env").write_text(f"SECRET_TOKEN={CANARY}\n", encoding="utf-8")


def pick_targets(skill_dir: Path, explicit):
    if explicit:
        return [skill_dir / s for s in explicit]
    out = []
    for ext in ("*.py", "*.sh"):
        out += sorted((skill_dir / "scripts").glob(ext)) if (skill_dir / "scripts").is_dir() else []
    return out


def run_in_docker(exe, image, skill_dir: Path, home: Path, rel_script: str,
                  timeout_s: int, trace: bool) -> dict:
    interp = "python" if rel_script.endswith(".py") else "sh"
    inner = ["timeout", str(timeout_s), interp, f"/skill/{rel_script}"]
    caps = []
    if trace:
        # strace writes to stderr; needs SYS_PTRACE (and seccomp unconfined to allow ptrace).
        inner = ["strace", "-f", "-e", "trace=connect,sendto,sendmsg,openat,execve",
                 "-s", "160"] + inner
        caps = ["--cap-add", "SYS_PTRACE", "--security-opt", "seccomp=unconfined"]
    cmd = [
        exe, "run", "--rm",
        "--network", "none",
        "--user", "1000:1000",
        "--cap-drop", "ALL", *caps,
        "--security-opt", "no-new-privileges",
        "--read-only",
        "--memory", "256m", "--cpus", "1", "--pids-limit", "128",
        "--tmpfs", "/tmp:rw,size=32m",
        "-e", "HOME=/home/sandbox",
        "-v", f"{skill_dir}:/skill:ro",
        "-v", f"{home}:/home/sandbox:rw",
        "-w", "/home/sandbox",
        image, *inner,
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s + 30)
        return {"script": rel_script, "exit": r.returncode, "traced": trace,
                "stdout": r.stdout[-4000:], "stderr": r.stderr[-8000:]}
    except subprocess.TimeoutExpired:
        return {"script": rel_script, "exit": None, "traced": trace,
                "stdout": "", "stderr": "[timed out]"}
    except Exception as e:
        return {"script": rel_script, "exit": None, "traced": trace,
                "stdout": "", "stderr": f"[run error: {e}]"}


OPENAT_RE = re.compile(r"openat\([^)]*\"([^\"]*(?:\.aws|\.ssh|\.env|credentials|id_rsa)[^\"]*)\"")
CONNECT_RE = re.compile(r"(connect|sendto|sendmsg)\(.*?(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})")
CONNECT6_RE = re.compile(r"inet_pton\(AF_INET6,\s*\"([0-9A-Fa-f:]+)\"|sin6_addr=[^)]*?\"([0-9A-Fa-f:]{4,})\"")


def scan_run(run: dict, home: Path):
    blob = (run.get("stdout", "") + "\n" + run.get("stderr", ""))
    hits = []
    reads = []
    if CANARY in blob:
        hits.append({"canary": CANARY, "where": f"stdout/stderr of {run['script']}",
                     "severity": "critical"})
    # files the script wrote into the fake home (canary staged for upload).
    # Identity-check against the actual planted files (not a basename blocklist), so a copy
    # to a NEW file literally named "credentials"/"id_rsa"/".env" is still flagged.
    planted = set()
    for rel in ((".aws", "credentials"), (".ssh", "id_rsa"), (".env",)):
        try:
            planted.add((home.joinpath(*rel)).resolve())
        except OSError:
            pass
    for f in home.rglob("*"):
        if f.is_file():
            try:
                txt = f.read_text(encoding="utf-8", errors="ignore")
                rp = f.resolve()
            except OSError:
                continue
            if CANARY in txt and rp not in planted:
                hits.append({"canary": CANARY, "where": f"file written: {f.relative_to(home)}",
                             "severity": "critical"})
    net = []
    low = blob.lower()
    for h in SUSPECT_HOST_HINTS:
        if h in low:
            net.append({"dest": h, "via": "stdout/stderr (egress blocked by --network none)"})
    # strace evidence (only present in --trace mode): secret-file opens + connect attempts
    if run.get("traced"):
        seen_reads = set()
        for m in OPENAT_RE.finditer(blob):
            p = m.group(1)
            if any(t in p for t in (".aws", ".ssh", ".env", "credentials", "id_rsa")) and p not in seen_reads:
                seen_reads.add(p)
                reads.append({"path": p, "via": f"openat() syscall in {run['script']}"})
        seen_net = set()
        for m in CONNECT_RE.finditer(blob):
            ip = m.group(2)
            if ip not in seen_net and not ip.startswith("127."):
                seen_net.add(ip)
                net.append({"dest": ip, "via": "connect()/sendto() syscall (blocked, but attempted)"})
        for m in CONNECT6_RE.finditer(blob):
            ip = m.group(1) or m.group(2)
            if ip and ip not in seen_net and not ip.startswith(("::1", "fe80", "::ffff:127")):
                seen_net.add(ip)
                net.append({"dest": ip, "via": "connect() IPv6 syscall (blocked, but attempted)"})
    return hits, net, reads


def main() -> int:
    ap = argparse.ArgumentParser(description="Dynamic sandbox execution (Docker)")
    ap.add_argument("skill_dir")
    ap.add_argument("--yes", action="store_true", help="actually execute (required)")
    ap.add_argument("--image", default=None, help="override image (default: auto)")
    ap.add_argument("--trace", action="store_true",
                    help="strace syscalls (catches secret openat + connect attempts)")
    ap.add_argument("--timeout", type=int, default=20)
    ap.add_argument("--script", action="append", default=[])
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    skill_dir = Path(args.skill_dir).resolve()
    targets = pick_targets(skill_dir, args.script)
    rels = [str(t.relative_to(skill_dir)).replace("\\", "/") for t in targets if t.exists()]

    result = {"skill_name": skill_dir.name, "ran": False, "skipped_reason": None,
              "image": None, "traced": args.trace,
              "scripts_executed": [], "network_attempts": [], "honeytoken_hits": [],
              "honeytoken_reads": [], "files_written_outside_workdir": [],
              "verdict_hint": "informational", "runs": []}

    ok, info = docker_available()
    exe = shutil.which("docker")
    # auto-select image: custom (strace+requests) if present, else slim fallback
    image = args.image
    if image is None and ok:
        have = subprocess.run([exe, "image", "inspect", DEFAULT_IMAGE],
                              capture_output=True, text=True)
        image = DEFAULT_IMAGE if have.returncode == 0 else FALLBACK_IMAGE
    image = image or FALLBACK_IMAGE
    result["image"] = image
    if args.trace and image == FALLBACK_IMAGE:
        # strace isn't in the slim image; trace silently no-ops there
        result["trace_note"] = ("--trace requested but custom image not built; "
                                "build assets/sandbox/Dockerfile as 'skill-review-sandbox' for strace")
        args.trace = False
        result["traced"] = False

    if not ok:
        result["skipped_reason"] = f"docker unavailable: {info}"
    elif not rels:
        result["skipped_reason"] = "no .py/.sh scripts to execute"
    elif not args.yes:
        result["skipped_reason"] = ("dry-run: pass --yes to execute. Would run "
                                    f"{rels} in {image} (network=none, non-root, "
                                    f"honeytokens planted{', strace' if args.trace else ''}).")
    else:
        with tempfile.TemporaryDirectory(prefix="skrv-home-") as tmp:
            home = Path(tmp)
            plant_honeytokens(home)
            for rel in rels:
                run = run_in_docker(exe, image, skill_dir, home, rel, args.timeout, args.trace)
                result["runs"].append(run)
                hits, net, reads = scan_run(run, home)
                result["honeytoken_hits"] += hits
                result["network_attempts"] += net
                result["honeytoken_reads"] += reads
            result["ran"] = True
            result["scripts_executed"] = rels
            if result["honeytoken_hits"] or result["honeytoken_reads"]:
                result["verdict_hint"] = "block"

    out = json.dumps(result, indent=2, ensure_ascii=False)
    if args.out:
        Path(args.out).write_text(out, encoding="utf-8")
        print(f"wrote {args.out} (ran={result['ran']}, image={image}, "
              f"hits={len(result['honeytoken_hits'])}, reads={len(result['honeytoken_reads'])}, "
              f"reason={result['skipped_reason']})")
    else:
        print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
