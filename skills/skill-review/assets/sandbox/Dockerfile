# Custom sandbox image for skill-review's dynamic layer.
# Adds `strace` (syscall tracing of connect/sendto/openat) and `requests` (so requests-based
# scripts actually execute instead of failing at import in the bare slim image).
# Build once:  docker build -t skill-review-sandbox <this dir>
# Network is only needed at BUILD time; the sandbox runs with --network none.
FROM python:3.12-slim
RUN apt-get update \
    && apt-get install -y --no-install-recommends strace \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir requests
# non-root default; sandbox_run.py also forces --user 1000:1000
RUN useradd -m -u 1000 sandbox || true
USER 1000:1000
