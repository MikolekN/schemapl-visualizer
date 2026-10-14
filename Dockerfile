FROM ghcr.io/astral-sh/uv:0.12.2-python3.11-trixie-slim AS build

RUN apt-get update \
    && apt-get install --yes --no-install-recommends \
       fonts-liberation fonts-texgyre-math fonts-atkinson-hyperlegible \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /fonts/licenses \
    && cp -r /usr/share/fonts/truetype/liberation \
       /usr/share/fonts/opentype/atkinson-hyperlegible \
       /usr/share/texmf/fonts/opentype/public/tex-gyre-math /fonts/ \
    && for package in fonts-liberation fonts-texgyre-math fonts-atkinson-hyperlegible; do \
         cp "/usr/share/doc/${package}/copyright" "/fonts/licenses/${package}"; \
       done

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-install-project --no-default-groups --extra service

COPY README.md MANIFEST.in LICENSE ./
COPY source/ source/
RUN uv sync --locked --no-editable --no-default-groups --extra service


FROM ghcr.io/astral-sh/uv:0.12.2-python3.11-dhi AS runtime

ENV PYTHONPATH="/app/site-packages:/app" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ="Europe/Warsaw"

COPY --from=build /fonts/ /usr/share/fonts/caise/
COPY --from=build --chown=65532:65532 \
    /app/.venv/lib/python3.*/site-packages/ /app/site-packages/
# The service's entry point and modules live in source/api/.
COPY --chown=65532:65532 source/api/ /app/
COPY --chown=65532:65532 LICENSE NOTICE /app/

WORKDIR /app
USER 65532
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/', timeout=3)"]

# --proxy-headers so redirects and logged client IPs stay correct behind nginx.
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--forwarded-allow-ips", "*"]
