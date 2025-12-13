#!/usr/bin/env bash
set -e

VENV_DIR=".venv"

echo "=== Checking for uv ==="
if command -v uv >/dev/null 2>&1; then
    echo "uv found — using uv venv + uv pip"

    if [ ! -d "$VENV_DIR" ]; then
        uv venv "$VENV_DIR"
    fi

    uv pip install -r requirements.txt

    echo "=== Running app.py ==="
    uv run streamlit run app.py

else
    echo "uv not found — using python -m venv"

    if [ ! -d "$VENV_DIR" ]; then
        python3 -m venv "$VENV_DIR"
    fi

    # shellcheck disable=SC1091
    source "$VENV_DIR/bin/activate"

    pip install -r requirements.txt

    echo "=== Running app.py ==="
    streamlit run app.py
fi
