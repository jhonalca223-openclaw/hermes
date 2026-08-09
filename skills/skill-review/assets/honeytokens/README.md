# Honeytokens

`sandbox_run.py` plants **canary credentials** into a throwaway HOME inside the Docker
container before executing a skill's scripts. The canary is a fresh random string per run
(shape `AKIACANARY<hex>`), embedded in fake `~/.aws/credentials`, `~/.ssh/id_rsa`, and
`~/.env`.

The point: these files contain no real secret, but **if the audited script reads them and
the canary later shows up** — in the script's stdout/stderr, in a file it writes, or in a
blocked outbound attempt's error — we have *dynamic proof* the script reached for the
planted secret at runtime. That is a forced-BLOCK signal (`dynamic.json.honeytoken_hits`).

These are generated at runtime, not stored here, so the canary can never be hardcoded into a
skill's allow-list. This directory exists to document the scheme; no static token files are
needed. To add extra decoys (e.g. a fake `~/.config/gcloud`), extend `plant_honeytokens()`
in `scripts/sandbox_run.py`.
