#!/usr/bin/env python3
"""
build_dmg.py - Standalone macOS DMG Installer Builder for League of Legends RPC

Creates a self-contained, high-fidelity macOS drag-and-drop disk image (.dmg):
  1. Stages a standalone 'League of Legends RPC.app' bundle.
  2. Embeds pruned runtime dependencies into Contents/Resources/site-packages
     (PyObjC Cocoa/WebKit, pypresence, Pillow, rumps).
  3. Configures universal launcher with auto-detection for macOS Python 3.
  4. Generates Retina 2x dark-themed installer background graphic.
  5. Includes Applications folder symlink, '⚡️ Instalación Rápida.command',
     and 'LEEME - Instrucciones.txt'.
  6. Compresses into read-only UDZO disk image via hdiutil.
  7. Verifies disk image and computes SHA-256 checksum for GitHub Releases.
"""

import os
import sys
import shutil
import hashlib
import plistlib
import subprocess
import argparse
from typing import Dict, Any, List

SOURCE_ROOT = os.path.dirname(os.path.abspath(__file__))
DIST_DIR = os.path.join(SOURCE_ROOT, "dist")
STAGING_DIR = os.path.join(DIST_DIR, "dmg_staging")
FINAL_DMG_NAME = "League_of_Legends_RPC_Installer.dmg"
FINAL_DMG_PATH = os.path.join(DIST_DIR, FINAL_DMG_NAME)
VOLUME_NAME = "League of Legends RPC"

RUNTIME_MODULES = [
    "app_gui.py",
    "assets_gen.py",
    "status_item.py",
    "popover_ui.py",
    "liquid_html.py",
    "discord_rpc_manager.py",
    "lol_champions.py",
    "lol_ranks.py",
]

AUXILIARY_ASSETS = [
    "AppIcon.icns",
    "triangle_logo.png",
    "triangle_logo_72.png",
    "triangle_menubar.png",
]

UNIVERSAL_LAUNCHER_SCRIPT = """#!/bin/bash
# League of Legends RPC - macOS Universal Launcher
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
CONTENTS="$( cd "$DIR/.." && pwd )"
RESOURCES="$CONTENTS/Resources"

# 1. Bundled dependencies take priority
if [ -d "$RESOURCES/site-packages" ]; then
    export PYTHONPATH="$RESOURCES/site-packages${PYTHONPATH:+:$PYTHONPATH}"
fi

# 2. Locate Python 3 Runtime
PYTHON_BIN=""
if [ -x "/usr/bin/python3" ]; then
    PYTHON_BIN="/usr/bin/python3"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
elif [ -x "/opt/homebrew/bin/python3" ]; then
    PYTHON_BIN="/opt/homebrew/bin/python3"
elif [ -x "/usr/local/bin/python3" ]; then
    PYTHON_BIN="/usr/local/bin/python3"
elif [ -x "/Users/victormanuel/discord-rpc/venv/bin/python3" ]; then
    PYTHON_BIN="/Users/victormanuel/discord-rpc/venv/bin/python3"
fi

if [ -z "$PYTHON_BIN" ]; then
    osascript -e 'display alert "Error de ejecución" message "No se encontró Python 3 en este Mac. Abre Terminal e instala las Command Line Tools ejecutando: xcode-select --install"'
    exit 1
fi

export TK_SILENCE_DEPRECATION=1
exec "$PYTHON_BIN" "$RESOURCES/app_gui.py" "$@"
"""

QUICK_INSTALL_COMMAND = """#!/bin/bash
# League of Legends RPC - Instalación Automática y Segura para macOS

clear
echo "==========================================================="
echo "   League of Legends RPC - Instalación Automática"
echo "==========================================================="
echo ""

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
APP_SRC="$DIR/League of Legends RPC.app"
APP_DEST="/Applications/League of Legends RPC.app"

if [ ! -d "$APP_SRC" ]; then
    echo "❌ Error: No se encontró 'League of Legends RPC.app' en este disco."
    read -p "Presiona Enter para salir..."
    exit 1
fi

echo "📦 1. Deteniendo instancias previas si existen..."
pkill -f "League of Legends RPC" >/dev/null 2>&1 || true
sleep 1

echo "📦 2. Instalando en /Applications..."
rm -rf "$APP_DEST"
cp -R "$APP_SRC" "$APP_DEST"

if [ -d "$APP_DEST" ]; then
    echo "   ✅ Aplicación instalada correctamente en /Applications."
else
    echo "   ❌ Error al copiar la aplicación a /Applications."
    read -p "Presiona Enter para salir..."
    exit 1
fi

echo "🛡️  3. Configurando permisos y removiendo atributos de cuarentena (Gatekeeper)..."
xattr -dr com.apple.quarantine "$APP_DEST" 2>/dev/null || true
chmod +x "$APP_DEST/Contents/MacOS/League of Legends RPC"
echo "   ✅ Permisos configurados."

echo ""
echo "🚀 4. ¿Deseas iniciar League of Legends RPC ahora mismo? (S/n): "
read -r respuesta
if [[ "$respuesta" =~ ^[nN]$ ]]; then
    echo "Puedes iniciar la app en cualquier momento desde tu carpeta Aplicaciones o Spotlight."
else
    echo "Iniciando League of Legends RPC..."
    open "$APP_DEST"
    echo "✅ ¡Iniciada! Busca el icono de Discord en tu barra de menús superior (junto al reloj)."
fi

echo ""
echo "==========================================================="
echo "   ¡Instalación completada exitosamente!"
echo "==========================================================="
echo ""
sleep 2
"""

README_INSTRUCTIONS_TXT = """=============================================================
  League of Legends RPC para macOS
  Discord Rich Presence • Selector Top 10 Juegos • Menubar App
=============================================================

¡Gracias por descargar League of Legends RPC!

MÉTODOS DE INSTALACIÓN:

Método 1 (Arrastrar y Soltar - Estándar de macOS):
1. Arrastra el icono "League of Legends RPC.app" hacia la carpeta "Applications" que ves al lado.
2. Abre tu carpeta Aplicaciones o presiona Cmd + Espacio (Spotlight) y escribe "League of Legends RPC".
3. Si macOS muestra una advertencia de seguridad por ser una app de desarrollador independiente:
   - Haz clic derecho (o Control + clic) sobre "League of Legends RPC" en Aplicaciones y selecciona "Abrir".
   - Haz clic en "Abrir" en la ventana emergente de confirmación (solo se requiere la primera vez).

Método 2 (Instalación Rápida Automática en 1 Clic):
1. Haz doble clic en el archivo "⚡️ Instalación Rápida.command".
2. Se abrirá una pequeña ventana de Terminal que:
   - Instalará la app en tu carpeta /Applications.
   - Removerá automáticamente la restricción de cuarentena de Gatekeeper.
   - Iniciará la aplicación inmediatamente.

CARACTERÍSTICAS INCLUIDAS:
- Soporte para League of Legends con 173 campeones oficiales (Riot Data Dragon CDN) y rangos (Hierro a Challenger).
- Selector integrado de los 10 Juegos Más Jugados:
  * League of Legends
  * VALORANT
  * Counter-Strike 2
  * Minecraft
  * Fortnite
  * Grand Theft Auto V
  * Apex Legends
  * Overwatch 2
  * Dota 2
  * Rocket League
  * Juego Personalizado (con cualquier Client ID de Discord Developer Portal)
- Control de duración de partidas y reinicio automático de estado.
- Interfaz flotante nativa Liquid Glass con tema oscuro.
- Opción de arranque automático con macOS al iniciar sesión.

Repositorio oficial, código fuente y soporte:
https://github.com/vcamachoone/Discord-RPC
"""


def compute_sha256(file_path: str) -> str:
    """Computes SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def stage_application_bundle(dest_app_path: str, bundle_deps: bool = True) -> bool:
    """
    Constructs a clean, self-contained macOS Application bundle at dest_app_path.
    """
    print(f"📦 Staging application bundle at: {dest_app_path}")
    os.makedirs(dest_app_path, exist_ok=True)

    contents_dir = os.path.join(dest_app_path, "Contents")
    macos_dir = os.path.join(contents_dir, "MacOS")
    resources_dir = os.path.join(contents_dir, "Resources")

    os.makedirs(macos_dir, exist_ok=True)
    os.makedirs(resources_dir, exist_ok=True)

    # 1. Info.plist
    plist_path = os.path.join(contents_dir, "Info.plist")
    plist_data = {
        "CFBundleExecutable": "League of Legends RPC",
        "CFBundleIconFile": "AppIcon",
        "CFBundleIdentifier": "com.victormanuel.lolrpc",
        "CFBundleName": "League of Legends RPC",
        "CFBundleDisplayName": "League of Legends",
        "CFBundlePackageType": "APPL",
        "CFBundleShortVersionString": "1.0.0",
        "CFBundleVersion": "1.0.0",
        "NSHighResolutionCapable": True,
        "LSUIElement": True,
    }
    with open(plist_path, "wb") as f:
        plistlib.dump(plist_data, f)
    print("  ✓ Created Contents/Info.plist (LSUIElement=True)")

    # 2. Universal Launcher
    launcher_path = os.path.join(macos_dir, "League of Legends RPC")
    with open(launcher_path, "w", encoding="utf-8") as f:
        f.write(UNIVERSAL_LAUNCHER_SCRIPT)
    os.chmod(launcher_path, 0o755)
    print("  ✓ Created executable Contents/MacOS/League of Legends RPC")

    # 3. Copy Runtime Python Modules
    for mod in RUNTIME_MODULES:
        src = os.path.join(SOURCE_ROOT, mod)
        dst = os.path.join(resources_dir, mod)
        if os.path.isfile(src):
            shutil.copy2(src, dst)
        else:
            raise FileNotFoundError(f"Missing required runtime module: {src}")
    print(f"  ✓ Copied {len(RUNTIME_MODULES)} core Python runtime modules")

    # 4. Copy assets directory
    src_assets = os.path.join(SOURCE_ROOT, "assets")
    dst_assets = os.path.join(resources_dir, "assets")
    if os.path.isdir(src_assets):
        if os.path.exists(dst_assets):
            shutil.rmtree(dst_assets)
        shutil.copytree(src_assets, dst_assets)
        print("  ✓ Copied assets/ directory")

    # 5. Copy Auxiliary Assets (AppIcon.icns, etc.)
    for asset in AUXILIARY_ASSETS:
        src = os.path.join(SOURCE_ROOT, asset)
        dst = os.path.join(resources_dir, asset)
        if os.path.isfile(src):
            shutil.copy2(src, dst)
    print("  ✓ Copied AppIcon.icns and auxiliary graphic resources")

    # 6. Bundle Pruned Site-Packages
    if bundle_deps:
        venv_sp = os.path.join(SOURCE_ROOT, "venv", "lib", "python3.9", "site-packages")
        if not os.path.isdir(venv_sp):
            print("  ⚠️ Warning: Virtual environment site-packages not found, skipping bundled libs.")
        else:
            dst_sp = os.path.join(resources_dir, "site-packages")
            if os.path.exists(dst_sp):
                shutil.rmtree(dst_sp)
            os.makedirs(dst_sp, exist_ok=True)

            ignored_prefixes = ("pip", "setuptools", "pkg_resources", "__pycache__", "_distutils")
            copied_count = 0
            for item in os.listdir(venv_sp):
                if item.startswith(ignored_prefixes):
                    continue
                s_item = os.path.join(venv_sp, item)
                d_item = os.path.join(dst_sp, item)
                if os.path.isdir(s_item):
                    shutil.copytree(s_item, d_item, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
                else:
                    shutil.copy2(s_item, d_item)
                copied_count += 1
            print(f"  ✓ Bundled {copied_count} pruned site-packages into Contents/Resources/site-packages")

    return True


def verify_staged_bundle(app_path: str) -> bool:
    """Verifies the staged bundle can import all required packages with system python3."""
    print("🔍 Verifying staged bundle integrity and importability...")
    sp_dir = os.path.join(app_path, "Contents", "Resources", "site-packages")
    if os.path.isdir(sp_dir):
        cmd = [
            "/usr/bin/python3",
            "-c",
            f'import sys; sys.path.insert(0, "{sp_dir}"); import Cocoa, WebKit, pypresence, PIL, rumps; print("Bundle import verification OK")',
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            print(f"  ❌ Bundle verification error: {res.stderr}")
            return False
        print("  ✓ Standalone system python3 import verification: PASS")
    return True


def build_dmg(output_dmg: str = FINAL_DMG_PATH, volume_name: str = VOLUME_NAME) -> str:
    """
    Builds the complete macOS DMG installer image.
    """
    print("\n" + "=" * 70)
    print("   Building League of Legends RPC macOS DMG Installer")
    print("=" * 70)

    # 1. Clean Staging and Dist directories
    if os.path.exists(STAGING_DIR):
        shutil.rmtree(STAGING_DIR)
    os.makedirs(STAGING_DIR, exist_ok=True)
    os.makedirs(DIST_DIR, exist_ok=True)

    # 2. Stage the application bundle
    staged_app = os.path.join(STAGING_DIR, "League of Legends RPC.app")
    stage_application_bundle(staged_app, bundle_deps=True)
    if not verify_staged_bundle(staged_app):
        raise RuntimeError("Bundle verification failed!")

    # 3. Create Applications symlink
    apps_symlink = os.path.join(STAGING_DIR, "Applications")
    if os.path.lexists(apps_symlink):
        os.unlink(apps_symlink)
    os.symlink("/Applications", apps_symlink)
    print("  ✓ Created Applications folder symlink")

    # 4. Generate Retina Background Image
    print("🎨 Generating Retina DMG background graphic...")
    try:
        from generate_dmg_background import generate_background
        bg_dir = os.path.join(STAGING_DIR, ".background")
        os.makedirs(bg_dir, exist_ok=True)
        bg_path = os.path.join(bg_dir, "background.png")
        generate_background(output_path=bg_path)
        print("  ✓ Background image embedded into .background/background.png")
    except Exception as e:
        print(f"  ⚠️ Could not generate custom background graphic: {e}")

    # 5. Add 1-Click Install Helper Command
    quick_install_path = os.path.join(STAGING_DIR, "⚡️ Instalación Rápida.command")
    with open(quick_install_path, "w", encoding="utf-8") as f:
        f.write(QUICK_INSTALL_COMMAND)
    os.chmod(quick_install_path, 0o755)
    print("  ✓ Created '⚡️ Instalación Rápida.command'")

    # 6. Add Readme / Instructions file
    readme_path = os.path.join(STAGING_DIR, "LEEME - Instrucciones.txt")
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(README_INSTRUCTIONS_TXT)
    print("  ✓ Created 'LEEME - Instrucciones.txt'")

    # 7. Remove destination DMG if already present
    if os.path.exists(output_dmg):
        os.remove(output_dmg)

    # 8. Create compressed UDZO DMG using hdiutil
    print(f"\n🔨 Creating compressed DMG disk image: {output_dmg}...")
    cmd = [
        "hdiutil",
        "create",
        "-volname",
        volume_name,
        "-srcfolder",
        STAGING_DIR,
        "-ov",
        "-format",
        "UDZO",
        "-imagekey",
        "zlib-level=9",
        output_dmg,
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"hdiutil failed with code {res.returncode}:\n{res.stderr}")
    print("  ✓ hdiutil create executed successfully")

    # 9. Verify DMG Integrity
    print("🔍 Verifying final DMG integrity...")
    verify_cmd = ["hdiutil", "verify", output_dmg]
    v_res = subprocess.run(verify_cmd, capture_output=True, text=True)
    if v_res.returncode != 0:
        print(f"  ⚠️ Warning: hdiutil verify reported an issue: {v_res.stderr}")
    else:
        print("  ✓ DMG verification: PASS")

    # 10. Clean up staging folder
    if os.path.exists(STAGING_DIR):
        shutil.rmtree(STAGING_DIR)

    # 11. Calculate file stats
    file_size_mb = os.path.getsize(output_dmg) / (1024 * 1024)
    sha256_hash = compute_sha256(output_dmg)

    print("\n" + "=" * 70)
    print("   🎉 DMG INSTALLER BUILT SUCCESSFULLY!")
    print("=" * 70)
    print(f"  File Name   : {os.path.basename(output_dmg)}")
    print(f"  Location    : {output_dmg}")
    print(f"  File Size   : {file_size_mb:.2f} MB")
    print(f"  Volume Name : {volume_name}")
    print(f"  SHA-256     : {sha256_hash}")
    print("=" * 70 + "\n")

    return output_dmg


def main() -> int:
    parser = argparse.ArgumentParser(description="Build macOS DMG Installer for League of Legends RPC.")
    parser.add_argument("--output", default=FINAL_DMG_PATH, help="Output DMG file path")
    parser.add_argument("--volname", default=VOLUME_NAME, help="Volume Name for the mounted DMG")
    args = parser.parse_args()

    try:
        build_dmg(output_dmg=args.output, volume_name=args.volname)
        return 0
    except Exception as e:
        print(f"❌ Error building DMG: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
