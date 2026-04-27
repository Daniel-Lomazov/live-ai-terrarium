# Build from the repository root with:
#   docker build -f infra/docker/glassbox/Dockerfile -t live-ai-terrarium-glassbox:v1 .
#
# This image is an inert sandbox baseline, not an application server. Run it with
# `--network none` and mount a workspace that already contains `.gb/outbox` and
# `.gb/cycles`, or let the host orchestrator create the workspace volume for you.
FROM python:3.12-slim-bookworm

LABEL org.opencontainers.image.title="live-ai-terrarium-glassbox" \
      org.opencontainers.image.description="Hardened single-container sandbox baseline for one Glass-Box runtime." \
      org.opencontainers.image.version="v1" \
      org.opencontainers.image.vendor="Live AI Terrarium"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HOME=/home/glassbox \
    PATH=/home/glassbox/.local/bin:/usr/local/bin:/usr/local/sbin:/usr/sbin:/usr/bin:/sbin:/bin

RUN apt-get update \
    && apt-get install --yes --no-install-recommends git tini \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 glassbox \
    && useradd --system --create-home --home-dir /home/glassbox --uid 10001 --gid 10001 --shell /usr/sbin/nologin glassbox \
    && mkdir -p /workspace/.gb/outbox /workspace/.gb/cycles /tmp/runtime \
    && chown -R glassbox:glassbox /workspace /home/glassbox /tmp/runtime

WORKDIR /workspace
USER 10001:10001

STOPSIGNAL SIGTERM

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import os,sys; ok=os.getuid() != 0 and os.path.isdir('/workspace/.gb/outbox') and os.path.isdir('/workspace/.gb/cycles'); sys.exit(0 if ok else 1)"

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["sleep", "infinity"]