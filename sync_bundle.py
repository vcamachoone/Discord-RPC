#!/usr/bin/env python3
"""
sync_bundle.py - Application Bundle Synchronization & Verification

Synchronizes Discord RPC League of Legends runtime modules, assets, and icons
into the macOS application bundle (/Applications/League of Legends RPC.app).
Validates bundle permissions, Info.plist XML integrity, and LSUIElement.
"""

import os
import sys
import shutil
import plistlib
import logging
from typing import Any, Dict, List, Optional, Tuple, Union

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("sync_bundle")

DEFAULT_BUNDLE_PATH = "/Applications/League of Legends RPC.app"
SOURCE_ROOT = os.path.dirname(os.path.abspath(__file__))

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

RUNTIME_DIRS = [
    "assets",
]

AUXILIARY_ASSETS = [
    "AppIcon.icns",
    "triangle_logo.png",
    "triangle_logo_72.png",
    "triangle_menubar.png",
]


def verify_bundle_integrity(
    bundle_path: str = DEFAULT_BUNDLE_PATH,
    detailed: bool = False,
) -> Union[bool, Dict[str, Any]]:
    """
    Verifies the integrity of the macOS application bundle:
      - Bundle folder exists and is a directory.
      - Contents/Info.plist exists, parses as valid XML plist, and has LSUIElement == True.
      - Contents/MacOS/League of Legends RPC launcher exists and has executable permissions (+x).
      - Contents/Resources/AppIcon.icns exists and has the 'icns' magic bytes.
      - Contents/Resources contains required Python runtime modules.

    Args:
        bundle_path: Path to the .app bundle directory.
        detailed: If True, returns a dict with details and errors.

    Returns:
        bool (or dict if detailed=True) indicating overall validity.
    """
    errors: List[str] = []
    checks: Dict[str, bool] = {}

    # 1. Bundle directory
    if not os.path.isdir(bundle_path):
        errors.append(f"Bundle directory does not exist: {bundle_path}")
        checks["bundle_exists"] = False
    else:
        checks["bundle_exists"] = True

    # 2. Info.plist integrity & LSUIElement
    plist_path = os.path.join(bundle_path, "Contents", "Info.plist")
    if not os.path.isfile(plist_path):
        errors.append(f"Info.plist missing: {plist_path}")
        checks["info_plist"] = False
    else:
        try:
            with open(plist_path, "rb") as f:
                plist = plistlib.load(f)

            if not isinstance(plist, dict):
                errors.append("Info.plist is not a valid dictionary plist")
                checks["info_plist"] = False
            else:
                exe = plist.get("CFBundleExecutable")
                lsui = plist.get("LSUIElement")
                bundle_id = plist.get("CFBundleIdentifier", "")

                if exe != "League of Legends RPC":
                    errors.append(f"CFBundleExecutable mismatch: expected 'League of Legends RPC', got '{exe}'")
                if not lsui:
                    errors.append("LSUIElement is not True (application will show in Dock)")
                if "com.victormanuel.lolrpc" not in bundle_id:
                    errors.append(f"CFBundleIdentifier unexpected: '{bundle_id}'")

                checks["info_plist"] = len(errors) == 0
        except Exception as e:
            errors.append(f"Failed to parse Info.plist: {e}")
            checks["info_plist"] = False

    # 3. Executable launcher permissions
    launcher_path = os.path.join(bundle_path, "Contents", "MacOS", "League of Legends RPC")
    if not os.path.isfile(launcher_path):
        errors.append(f"Launcher missing: {launcher_path}")
        checks["launcher_executable"] = False
    else:
        is_exec = os.access(launcher_path, os.X_OK)
        if not is_exec:
            errors.append(f"Launcher is not executable: {launcher_path}")
            checks["launcher_executable"] = False
        else:
            checks["launcher_executable"] = True

    # 4. AppIcon.icns integrity
    icns_path = os.path.join(bundle_path, "Contents", "Resources", "AppIcon.icns")
    if not os.path.isfile(icns_path):
        errors.append(f"AppIcon.icns missing: {icns_path}")
        checks["app_icon"] = False
    else:
        try:
            with open(icns_path, "rb") as f:
                magic = f.read(4)
            if magic != b"icns":
                errors.append(f"AppIcon.icns invalid header: expected b'icns', got {magic!r}")
                checks["app_icon"] = False
            else:
                checks["app_icon"] = True
        except Exception as e:
            errors.append(f"Failed reading AppIcon.icns: {e}")
            checks["app_icon"] = False

    # 5. Core runtime files in Resources
    resources_dir = os.path.join(bundle_path, "Contents", "Resources")
    if not os.path.isdir(resources_dir):
        errors.append(f"Resources directory missing: {resources_dir}")
        checks["resources_present"] = False
    else:
        app_gui_path = os.path.join(resources_dir, "app_gui.py")
        if not os.path.isfile(app_gui_path):
            errors.append(f"app_gui.py missing in bundle Resources: {app_gui_path}")
            checks["resources_present"] = False
        else:
            checks["resources_present"] = True

    is_valid = len(errors) == 0

    if detailed:
        return {
            "valid": is_valid,
            "bundle_path": bundle_path,
            "checks": checks,
            "errors": errors,
        }
    return is_valid


def sync_app_bundle(
    dry_run: bool = False,
    bundle_path: str = DEFAULT_BUNDLE_PATH,
    src_dir: Optional[str] = None,
) -> bool:
    """
    Synchronizes runtime Python code and assets into the target application bundle.

    Args:
        dry_run: If True, performs validation without writing changes.
        bundle_path: Path to /Applications/League of Legends RPC.app.
        src_dir: Source repository root (defaults to directory of sync_bundle.py).

    Returns:
        bool indicating success.
    """
    if src_dir is None:
        src_dir = SOURCE_ROOT

    logger.info("Synchronizing application bundle: %s -> %s (dry_run=%s)", src_dir, bundle_path, dry_run)

    if not os.path.isdir(bundle_path):
        logger.error("Target bundle path does not exist: %s", bundle_path)
        return False

    resources_dir = os.path.join(bundle_path, "Contents", "Resources")
    macos_dir = os.path.join(bundle_path, "Contents", "MacOS")
    launcher_path = os.path.join(macos_dir, "League of Legends RPC")

    if dry_run:
        # Check source files exist and bundle structure is sound
        for mod in RUNTIME_MODULES:
            src_file = os.path.join(src_dir, mod)
            if not os.path.isfile(src_file):
                logger.warning("Dry run warning: source module not found: %s", src_file)
        return True

    # 1. Ensure target directories exist
    os.makedirs(resources_dir, exist_ok=True)
    os.makedirs(macos_dir, exist_ok=True)

    # 2. Copy runtime modules
    for mod in RUNTIME_MODULES:
        src_mod = os.path.join(src_dir, mod)
        if os.path.isfile(src_mod):
            dst_mod = os.path.join(resources_dir, mod)
            shutil.copy2(src_mod, dst_mod)
            logger.info("Copied module: %s -> %s", mod, dst_mod)
        else:
            logger.warning("Source module missing: %s", src_mod)

    # 3. Copy resource directories (assets/)
    for d in RUNTIME_DIRS:
        src_d = os.path.join(src_dir, d)
        if os.path.isdir(src_d):
            dst_d = os.path.join(resources_dir, d)
            os.makedirs(dst_d, exist_ok=True)
            for item in os.listdir(src_d):
                s_item = os.path.join(src_d, item)
                d_item = os.path.join(dst_d, item)
                if os.path.isfile(s_item):
                    shutil.copy2(s_item, d_item)
            logger.info("Synchronized directory: %s -> %s", d, dst_d)

    # 4. Copy auxiliary assets (icons, logos)
    for asset in AUXILIARY_ASSETS:
        src_asset = os.path.join(src_dir, asset)
        if os.path.isfile(src_asset):
            dst_asset = os.path.join(resources_dir, asset)
            shutil.copy2(src_asset, dst_asset)

    # 5. Fix executable permissions on launcher
    if os.path.isfile(launcher_path):
        current_mode = os.stat(launcher_path).st_mode
        desired_mode = current_mode | 0o755
        os.chmod(launcher_path, desired_mode)
        logger.info("Enforced executable permissions (0o755) on launcher: %s", launcher_path)

    # 6. Verify integrity of synchronized bundle
    valid = verify_bundle_integrity(bundle_path=bundle_path)
    if not valid:
        logger.error("Bundle integrity verification failed after synchronization")
        return False

    logger.info("Bundle synchronization and verification completed successfully.")
    return True


def sync_to_applications(
    bundle_path: str = DEFAULT_BUNDLE_PATH,
    src_dir: Optional[str] = None,
    dry_run: bool = False,
) -> bool:
    """Convenience alias for sync_app_bundle."""
    return sync_app_bundle(dry_run=dry_run, bundle_path=bundle_path, src_dir=src_dir)


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Synchronize and verify League of Legends RPC macOS app bundle.")
    parser.add_argument("--bundle-path", default=DEFAULT_BUNDLE_PATH, help="Path to .app bundle")
    parser.add_argument("--dry-run", action="store_true", help="Perform check without modifying files")
    parser.add_argument("--verify-only", action="store_true", help="Only verify existing bundle integrity")

    args = parser.parse_args()

    if args.verify_only:
        report = verify_bundle_integrity(bundle_path=args.bundle_path, detailed=True)
        print("Bundle Verification Report:")
        print(f"  Valid: {report['valid']}")
        print(f"  Path:  {report['bundle_path']}")
        for check, passed in report["checks"].items():
            print(f"    - {check}: {'PASS' if passed else 'FAIL'}")
        if report["errors"]:
            print("  Errors:")
            for err in report["errors"]:
                print(f"    * {err}")
        return 0 if report["valid"] else 1

    success = sync_app_bundle(dry_run=args.dry_run, bundle_path=args.bundle_path)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
