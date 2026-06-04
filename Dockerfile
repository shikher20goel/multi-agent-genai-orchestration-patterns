# Pinned reproduction environment for AgentOrchPatterns (task 050).
#
# Base image pin: python:3.11-slim. For a fully immutable build, pin
# the digest of the python:3.11-slim image you build from, e.g.:
#   FROM python:3.11-slim@sha256:<digest-of-python-3.11-slim>
# (digest intentionally left as a comment slot: this build environment
# has no registry access to resolve the current digest; resolve with
# `docker buildx imagetools inspect python:3.11-slim` and pin it.)
FROM python:3.11-slim

LABEL org.opencontainers.image.title="agentorch" \
      org.opencontainers.image.description="Reproducibility package for 'A Pattern Catalog for Multi-Agent Generative AI Orchestration Across Enterprise CRM and Hyperscaler Cloud Platforms' (IEEE Access submission)" \
      org.opencontainers.image.authors="Shikher Goel" \
      org.opencontainers.image.licenses="Apache-2.0"

# Headless matplotlib; never buffer logs; never write .pyc files.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MPLBACKEND=Agg \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Non-root user (best practice).
RUN useradd --create-home --shell /usr/sbin/nologin agentorch
WORKDIR /opt/agentorch

# Install the pinned dependency closure first (layer-cache friendly).
COPY environment/requirements.lock environment/requirements.lock
RUN python -m pip install --no-cache-dir -r environment/requirements.lock

# Copy the package and install it without re-resolving dependencies.
COPY . .
RUN python -m pip install --no-cache-dir --no-deps -e . \
    && chown -R agentorch:agentorch /opt/agentorch

USER agentorch

# Full reproduction (study -> tables -> figures). No network is used.
CMD ["bash", "run.sh"]
