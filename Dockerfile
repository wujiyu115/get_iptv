# Stage 1: frontend
FROM oven/bun:1-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json ./
RUN bun install
COPY frontend/ ./
RUN bun run build

# Stage 2: python deps — uv and its cache stay here, never reach the final image
FROM python:3.13-alpine AS deps
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/
WORKDIR /app
COPY backend/requirements.txt ./
# pytest is dev-only; the production image never runs tests
RUN sed -i '/^pytest/d' requirements.txt \
    && uv venv /opt/venv \
    && uv pip install --python /opt/venv/bin/python -r requirements.txt

# Stage 3: production — Alpine's ffmpeg is a fraction of Debian's dep tree
FROM python:3.13-alpine
RUN apk add --no-cache ffmpeg
WORKDIR /app
COPY --from=deps /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
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
