# Dynamic Sandbox — Backend & Platform Notes

## Backend: Docker (not Windows Sandbox)

Windows 11 **Home** does not ship the built-in *Windows Sandbox* feature (it is Pro/
Enterprise/Education only), so the dynamic layer uses **Docker** instead. This machine has
Docker (verified `docker --version` → 29.4.2) with the WSL2 `docker-desktop` backend.

**Docker Desktop must be running.** Its WSL distro can be `Stopped`; `sandbox_run.py` calls
`docker info` first and, if the daemon is not up (or Docker is absent), it **degrades**:
`dynamic.json` gets `ran:false` and a `skipped_reason`, and the verdict is reported as
"static-only" rather than silently PASSing. Start Docker Desktop to enable the dynamic pass.

First run pulls `python:3.12-slim` (override with `--image`).

## Lockdown applied to every run

`docker run --rm --network none --user 1000:1000 --cap-drop ALL
--security-opt no-new-privileges --read-only --memory 256m --cpus 1 --pids-limit 128
--tmpfs /tmp ... timeout <N> <interp> /skill/<script>`

- **`--network none`** — no real egress is possible; a network-exfil attempt fails. We still
  detect it because the destination host typically appears in the script's error/traceback
  (scanned for suspicious destinations), and because the **honeytoken read** is observable.
- **Non-root, all caps dropped, no-new-privileges, read-only rootfs** — minimizes what a
  malicious script can do even inside the container.
- **Resource + pid limits + hard `timeout`** — contains fork bombs / runaways.
- **Explicit `--yes` required** — executing untrusted code is a real action; without it the
  script only prints its plan. The orchestrator confirms with the user per skill.

## Image: build the custom sandbox

`sandbox_run.py` auto-selects the **`skill-review-sandbox`** image if present, else falls back
to `python:3.12-slim`. Build the custom image once (it adds `requests` so requests-based
scripts actually execute instead of failing at import, and `strace` for syscall tracing):

```
docker build -t skill-review-sandbox assets/sandbox
```

Network is needed only at build time; the sandbox always runs with `--network none`.

## Detection scope (and honest limits)

What the dynamic pass catches:
- **Honeytoken reads** — the canary appears in stdout/stderr or a written file, **or**
  (with `--trace`) an `openat()` of a planted secret file is observed → the script reached the
  planted secret even if it printed/staged nothing (forced BLOCK).
- **Connection attempts** — with `--trace`, `connect()`/`sendto()` syscalls are captured even
  though egress is blocked, so an exfil attempt is visible by its target; without trace, a
  blocked egress often still names the host in the error/traceback (scanned for suspicious
  destinations).
- `--trace` adds `--cap-add SYS_PTRACE --security-opt seccomp=unconfined` (needed for ptrace);
  this slightly loosens the sandbox, so it is opt-in. Requires the custom image (strace).

What it still does **not** do (documented gaps, not silent):
- A catch-all network sink that records full request bodies on an isolated network.
- Executing PowerShell/`.ps1` or compiled binaries — the image runs `.py`/`.sh` only;
  PowerShell is covered by **static** analysis (prescan + reviewers). A
  `mcr.microsoft.com/powershell` image could be added if needed.
- Time-bombed/conditional payloads that don't fire during the short traced run.

Because of these limits, the dynamic layer **augments** the static review; it never replaces
it. A clean dynamic run does not by itself produce PASS — the static findings still govern.

## Cross-platform housekeeping (all OSes)

- All scripts use `pathlib` + explicit `encoding="utf-8"` (avoids Windows cp1252/gbk
  mojibake — note `init_skill.py` from skill-creator crashes on emoji prints under gbk; run
  skill-review's own scripts with `PYTHONUTF8=1` if the host console is non-UTF-8).
- `discover_skills.py` resolves symlinks and dedupes by realpath — required here because
  `~/.claude/skills` symlinks many `lark-*` into `~/.agents/skills`.
- Signature library in `prescan.py` covers both PowerShell and POSIX dangerous-command
  forms, so static detection is OS-agnostic regardless of where the dynamic layer can run.
