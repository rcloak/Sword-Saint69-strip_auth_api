#!/usr/bin/env bash
set -e

python -m pip install --upgrade pip
pip install -r requirements.txt

exec uvicorn api:app --host 0.0.0.0 --port "${PORT:-8000}"
