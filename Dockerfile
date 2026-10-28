# prism-ai-lint as a container: lint the configuration of the mounted directory.
#   docker run --rm -v "$PWD:/w" chrysa/prism-ai-lint .
# The image installs the wheel built by the release workflow (dist/*.whl).
# python:3.13-slim, pinned by digest
FROM python@sha256:2d44738ebf4ce5f63b9d9ea871e9c7cfdc0426f7b0c97cac915fd88ded1d86bb

LABEL org.opencontainers.image.title="prism-ai-lint" \
      org.opencontainers.image.description="Linter, fixer and guard for AI coding-agent configuration." \
      org.opencontainers.image.source="https://github.com/chrysa/prism-ai-lint" \
      org.opencontainers.image.licenses="Apache-2.0"

COPY dist/*.whl /tmp/dist/
RUN python -m pip install --no-cache-dir --only-binary :all: /tmp/dist/*.whl \
    && rm -rf /tmp/dist \
    && useradd --create-home --uid 10001 lint

USER lint
WORKDIR /w

# A one-shot CLI, not a service: there is nothing to probe.
HEALTHCHECK NONE

ENTRYPOINT ["prism-ai-lint"]
CMD ["--help"]
