FROM python:3.12-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt playwright==1.63.0 && \
    python -m playwright install --with-deps chromium
COPY app ./app
RUN useradd --create-home --uid 10001 archive && \
    mkdir -p /data/evidence && \
    chown -R archive:archive /data/evidence /ms-playwright
USER archive
CMD ["python", "-m", "app.worker.capture"]
