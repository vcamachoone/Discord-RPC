#!/bin/bash
# League of Legends RPC - Universal App Launcher
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
CONTENTS="$( cd "$DIR/.." && pwd )"
RESOURCES="$CONTENTS/Resources"

# 1. Bundled dependencies take priority if packaged
if [ -d "$RESOURCES/site-packages" ]; then
    export PYTHONPATH="$RESOURCES/site-packages${PYTHONPATH:+:$PYTHONPATH}"
fi

# 2. Locate Python 3 Runtime
PYTHON_BIN=""
if [ -x "$DIR/../../venv/bin/python3" ]; then
    PYTHON_BIN="$DIR/../../venv/bin/python3"
elif [ -x "/Users/victormanuel/discord-rpc/venv/bin/python3" ]; then
    PYTHON_BIN="/Users/victormanuel/discord-rpc/venv/bin/python3"
elif [ -x "/usr/bin/python3" ]; then
    PYTHON_BIN="/usr/bin/python3"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
elif [ -x "/opt/homebrew/bin/python3" ]; then
    PYTHON_BIN="/opt/homebrew/bin/python3"
elif [ -x "/usr/local/bin/python3" ]; then
    PYTHON_BIN="/usr/local/bin/python3"
fi

if [ -z "$PYTHON_BIN" ]; then
    osascript -e 'display alert "Error de ejecución" message "No se encontró Python 3 en este Mac. Abre Terminal e instala las Command Line Tools con: xcode-select --install"'
    exit 1
fi

export TK_SILENCE_DEPRECATION=1
exec "$PYTHON_BIN" "$RESOURCES/app_gui.py" "$@"
