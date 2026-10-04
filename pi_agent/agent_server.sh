#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
VENV_DIR="$SCRIPT_DIR/.venv"
PYTHON="$VENV_DIR/bin/python"
REQUIREMENTS="$SCRIPT_DIR/requirements.txt"
REQUIREMENTS_STAMP="$VENV_DIR/.requirements.sha256"
USE_HARDWARE=0

for argument in "$@"; do
    if [[ "$argument" == "--hardware" ]]; then
        USE_HARDWARE=1
    fi
done

if [[ ! -x "$PYTHON" ]]; then
    echo "Creating Pi virtual environment..."
    python3 -m venv "$VENV_DIR"
fi

if [[ "$USE_HARDWARE" -eq 1 ]]; then
    REQUIREMENTS_HASH="$(sha256sum "$REQUIREMENTS" | cut -d ' ' -f 1)"
    INSTALLED_HASH=""
    if [[ -f "$REQUIREMENTS_STAMP" ]]; then
        INSTALLED_HASH="$(cat "$REQUIREMENTS_STAMP")"
    fi
    if [[ "$INSTALLED_HASH" != "$REQUIREMENTS_HASH" ]]; then
        echo "Installing Pi LED hardware requirements..."
        "$PYTHON" -m pip install -r "$REQUIREMENTS"
        printf '%s' "$REQUIREMENTS_HASH" > "$REQUIREMENTS_STAMP"
    fi
fi

TOKEN_DIRECTORY="${XDG_CONFIG_HOME:-$HOME/.config}/3dXmasTree"
TOKEN_FILE="$TOKEN_DIRECTORY/agent-token"
mkdir -p "$TOKEN_DIRECTORY"
chmod 700 "$TOKEN_DIRECTORY"

if [[ -n "${XMAS_AGENT_TOKEN:-}" ]]; then
    TOKEN="$XMAS_AGENT_TOKEN"
    printf '%s' "$TOKEN" > "$TOKEN_FILE"
    chmod 600 "$TOKEN_FILE"
elif [[ -f "$TOKEN_FILE" ]]; then
    TOKEN="$(cat "$TOKEN_FILE")"
else
    read -r -s -p "Paste the shared PC agent token: " TOKEN
    printf '\n'
    if [[ -z "$TOKEN" ]]; then
        echo "The shared agent token cannot be empty." >&2
        exit 1
    fi
    (umask 077 && printf '%s' "$TOKEN" > "$TOKEN_FILE")
fi

export XMAS_AGENT_TOKEN="$TOKEN"
echo "Starting Pi agent in $([[ "$USE_HARDWARE" -eq 1 ]] && echo hardware || echo simulation) mode..."
exec "$PYTHON" "$SCRIPT_DIR/agent_server.py" "$@"
