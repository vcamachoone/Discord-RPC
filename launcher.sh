#!/bin/bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
RESOURCES="$DIR/../Resources"
export TK_SILENCE_DEPRECATION=1
exec /Users/victormanuel/discord-rpc/venv/bin/python3 "$RESOURCES/app_gui.py"
