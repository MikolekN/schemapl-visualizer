FROM python:3.12-slim-trixie

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Fonts for the PDF layout: Liberation Serif (Times New Roman's metrics) and
# TeX Gyre Termes Math, and Atkinson Hyperlegible for the accessible version
# (packaged since Debian trixie). The math font is installed in the TeX tree,
# which Typst does not search: linked.
RUN apt-get update \
    && apt-get install --yes --no-install-recommends \
       fonts-liberation fonts-texgyre-math fonts-atkinson-hyperlegible \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /usr/share/fonts/opentype \
    && ln -s /usr/share/texmf/fonts/opentype/public/tex-gyre-math /usr/share/fonts/opentype/tex-gyre-math

WORKDIR /srv

COPY requirements.txt ./
RUN pip install --no-cache-dir --requirement requirements.txt

COPY app ./app

RUN useradd --system --create-home --uid 10001 appuser
USER appuser

# --proxy-headers so redirects and logged client IPs stay correct behind nginx.
CMD ["uvicorn", "app.service:app", \
     "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--forwarded-allow-ips", "*"]
