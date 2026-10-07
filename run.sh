#!/usr/bin/env bash
# Zero-install launcher: needs only uv (https://docs.astral.sh/uv/) and Docker access.
#   ./run.sh                 serve the UI on 127.0.0.1:9780
#   ./run.sh --once          print the catalog and exit
#   ./run.sh --demo          try it with sample data
cd "$(dirname "$0")" || exit 1
export DATA_DIR="${DATA_DIR:-$PWD/data}"
exec uv run --no-project --with "fastapi>=0.110" --with "uvicorn>=0.29" --with "docker>=7.0" python -m app.main "$@"
