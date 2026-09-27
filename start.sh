#!/bin/bash
pkill -f "app_gui.py" 2>/dev/null
pkill -f "lol_rpc.py" 2>/dev/null
open "/Applications/League of Legends RPC.app"
echo "✅ League of Legends Menu Bar iniciado en segundo plano."
