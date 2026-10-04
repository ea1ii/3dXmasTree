#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
VENV_DIR="$SCRIPT_DIR/.venv"
PYTHON="$VENV_DIR/bin/python"
STAMP="$VENV_DIR/.animation-requirements.sha256"

if [[ ! -x "$PYTHON" ]]; then
    echo "Creating Pi virtual environment..."
    python3 -m venv "$VENV_DIR"
fi

REQUIREMENT_FILES=()
for argument in "$@"; do
    if [[ "$argument" == "--hardware" ]]; then
        REQUIREMENT_FILES+=("$SCRIPT_DIR/requirements.txt")
    fi
done
while IFS= read -r file; do
    REQUIREMENT_FILES+=("$file")
done < <(find "$REPO_ROOT/common/animations" -name 'requirements*.txt' -type f | sort)

FINGERPRINT="$(sha256sum "${REQUIREMENT_FILES[@]}" | sha256sum | cut -d ' ' -f 1)"
if [[ "$(cat "$STAMP" 2>/dev/null || true)" != "$FINGERPRINT" ]]; then
    for file in "${REQUIREMENT_FILES[@]}"; do
        echo "Installing dependencies from $file..."
        "$PYTHON" -m pip install -r "$file"
    done
    printf '%s' "$FINGERPRINT" > "$STAMP"
fi

exec "$PYTHON" "$SCRIPT_DIR/3dXmasTree.py" "$@"
