# Throwaway environment for collect_facts.py. The script runs code from
# third-party catalogs, so it runs here and not on the host.
FROM python:3.12-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends git ca-certificates \
 && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.9.5 /uv /uvx /usr/local/bin/

ENV UV_CACHE_DIR=/tmp/uv-cache \
    HOME=/tmp

# Match pins.toml [rashid].
ARG RASHID_VERSION=0.3.0
RUN UV_TOOL_DIR=/opt/uv-tools UV_TOOL_BIN_DIR=/usr/local/bin \
      uv tool install "rashid==${RASHID_VERSION}" \
 && chmod -R a+rX /opt/uv-tools \
 && rm -rf /tmp/uv-cache

COPY freeze-case.sh /usr/local/bin/freeze-case
ENTRYPOINT ["freeze-case"]
