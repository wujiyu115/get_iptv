#!/bin/bash
set -e
PORT="${1:-5180}"; export PORT
command -v bun >/dev/null 2>&1 || { echo "错误: 未找到 bun"; exit 1; }
command -v uv  >/dev/null 2>&1 || { echo "错误: 未找到 uv"; exit 1; }

cd "$(dirname "$0")/frontend"
bun install
bun run build:dev
bun run build:dev -- --watch &
FRONTEND_PID=$!

cd ../backend
[ ! -f config.yaml ] && [ -f config.yaml.example ] && cp config.yaml.example config.yaml
[ ! -d .venv ] && uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
python run_dev.py &
BACKEND_PID=$!

trap "kill $FRONTEND_PID $BACKEND_PID 2>/dev/null; exit" INT
wait
