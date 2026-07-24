# Stage 1: frontend
FROM oven/bun:1-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json ./
RUN bun install
COPY frontend/ ./
RUN bun run build

# Stage 2: production
FROM python:3.13-slim AS production
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/
COPY backend/requirements.txt ./
RUN uv pip install --system -r requirements.txt
COPY backend/ ./
COPY --from=frontend-build /app/frontend/dist ./frontend/dist
ENV FRONTEND=/app/frontend/dist
ENV PORT=5180
ENV OUTPUT_DIR=/app/output
ENV DB_PATH=/app/data/iptv.db
RUN mkdir -p /app/logs /app/output /app/data
EXPOSE 5180
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5180/api/tasks/status')" || exit 1
CMD ["python", "run_prod.py"]
