FROM python:3.11-slim-trixie

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install --yes --no-install-recommends \
       fonts-liberation fonts-texgyre-math fonts-atkinson-hyperlegible \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /usr/share/fonts/opentype \
    && ln -s /usr/share/texmf/fonts/opentype/public/tex-gyre-math /usr/share/fonts/opentype/tex-gyre-math

WORKDIR /srv

COPY requirements.txt ./
RUN pip install --no-cache-dir --requirement requirements.txt

COPY pyproject.toml README.md MANIFEST.in LICENSE /tmp/build/
COPY source/schemapl_visualizer/ /tmp/build/source/schemapl_visualizer/
RUN pip install --no-cache-dir --no-deps /tmp/build \
    && rm -rf /tmp/build

COPY source/api/ ./

RUN useradd --system --create-home --uid 10001 appuser
USER appuser

CMD ["uvicorn", "main:app", \
     "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--forwarded-allow-ips", "*"]
