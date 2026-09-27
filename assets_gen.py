#!/usr/bin/env python3
"""
assets_gen.py - Dynamic Status Icons Generator for Discord RPC (macOS Menubar)

Generates menubar status icon PNG assets matching design specifications (123.png):
  - 'normal': Discord Clyde logo in monochrome white (for macOS template mode).
  - 'active': Discord Clyde logo in white with a vibrant circular blue dot (#00A8FC,
              diameter 6-7pt) in the lower-right corner with a cutout ring.
  - 'paused': Discord Clyde logo rendered with 35% alpha (dimmed/grayed out).

Renders both Retina @2x (44x44 px, 22x22 pt) and standard 1x (22x22 px) resolutions.
Provides:
  - generate_status_icons(output_dir: str) -> Dict[str, str]
  - CLI entry point with configurable output directory.
"""

import os
import sys
import argparse
from typing import Dict, Optional, Tuple

# Official Discord Clyde vector geometry
DISCORD_CLYDE_PATH = (
    "M107.7,8.07A105.15,105.15,0,0,0,81.47,0a72.06,72.06,0,0,0-3.36,6.83"
    "A97.68,97.68,0,0,0,49,6.83,72.37,72.37,0,0,0,45.64,0,105.89,105.89,0,0,0,19.39,8.09"
    "C2.79,32.65-1.71,56.6.54,80.21h0A105.73,105.73,0,0,0,32.71,96.36,77.7,77.7,0,0,0,39.6,85.25"
    "a68.42,68.42,0,0,1-10.85-5.18c.91-.66,1.8-1.34,2.66-2a75.57,75.57,0,0,0,64.32,0"
    "c.87.71,1.76,1.39,2.66,2a68.68,68.68,0,0,1-10.87,5.19,77,77,0,0,0,6.89,11.1"
    "A105.25,105.25,0,0,0,126.6,80.22h0C129.24,52.84,122.09,29.11,107.7,8.07Z"
    "M42.45,65.69C36.18,65.69,31,60,31,53s5-12.74,11.43-12.74S54,45.91,53.89,53,48.84,65.69,42.45,65.69Zm42.24,0"
    "C78.41,65.69,73.25,60,73.25,53s5-12.74,11.44-12.74S96.23,45.91,96.12,53,91.08,65.69,84.69,65.69Z"
)
CLYDE_VIEWBOX_W = 127.14
CLYDE_VIEWBOX_H = 96.36

# Design parameters in points (for 22x22 pt menubar square item)
CANVAS_POINTS = 22.0
CLYDE_X_PT = 2.0
CLYDE_Y_PT = 4.2
CLYDE_W_PT = 18.0
CLYDE_H_PT = 13.65

# Lower-right status indicator dot (#00A8FC) parameters
# Diameter 6.2 pt (spec 6-7 pt), contained strictly within border bounds (x <= 20.6 pt)
CUTOUT_X_PT = 13.6
CUTOUT_Y_PT = 1.7
CUTOUT_SIZE_PT = 7.8

DOT_X_PT = 14.4
DOT_Y_PT = 2.5
DOT_SIZE_PT = 6.2

# Color definitions
DOT_COLOR_HEX = "#00A8FC"
DOT_COLOR_RGB = (0, 168, 252)  # R:0, G:168, B:252
PAUSED_ALPHA = 0.35


def _render_icon_cocoa(state: str, pixels_wide: int, pixels_high: int) -> bytes:
    """
    Renders an icon state directly using Apple Cocoa / AppKit CoreGraphics.
    Produces high-fidelity anti-aliased bitmap output at native resolution.
    """
    import AppKit
    from Foundation import NSData

    svg_data = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {CLYDE_VIEWBOX_W} {CLYDE_VIEWBOX_H}">'
        f'<path fill="white" d="{DISCORD_CLYDE_PATH}"/>'
        f'</svg>'
    ).encode("utf-8")

    ns_data = NSData.dataWithBytes_length_(svg_data, len(svg_data))
    clyde_img = AppKit.NSImage.alloc().initWithData_(ns_data)
    if not clyde_img:
        raise RuntimeError("Failed to create NSImage from Clyde SVG vector.")

    rep = AppKit.NSBitmapImageRep.alloc().initWithBitmapDataPlanes_pixelsWide_pixelsHigh_bitsPerSample_samplesPerPixel_hasAlpha_isPlanar_colorSpaceName_bytesPerRow_bitsPerPixel_(
        None, pixels_wide, pixels_high, 8, 4, True, False, AppKit.NSCalibratedRGBColorSpace, 0, 32
    )
    rep.setSize_(AppKit.NSMakeSize(CANVAS_POINTS, CANVAS_POINTS))

    AppKit.NSGraphicsContext.saveGraphicsState()
    try:
        ctx = AppKit.NSGraphicsContext.graphicsContextWithBitmapImageRep_(rep)
        AppKit.NSGraphicsContext.setCurrentContext_(ctx)

        # Fraction (alpha) depends on state
        alpha = PAUSED_ALPHA if state == "paused" else 1.0

        # Draw Clyde logo
        clyde_img.drawInRect_fromRect_operation_fraction_(
            AppKit.NSMakeRect(CLYDE_X_PT, CLYDE_Y_PT, CLYDE_W_PT, CLYDE_H_PT),
            AppKit.NSMakeRect(0, 0, CLYDE_VIEWBOX_W, CLYDE_VIEWBOX_H),
            AppKit.NSCompositingOperationSourceOver,
            alpha,
        )

        # For active state, punch out cutout ring and draw the vibrant #00A8FC dot
        if state == "active":
            # Cutout ring
            ctx.setCompositingOperation_(AppKit.NSCompositingOperationClear)
            cutout_path = AppKit.NSBezierPath.bezierPathWithOvalInRect_(
                AppKit.NSMakeRect(CUTOUT_X_PT, CUTOUT_Y_PT, CUTOUT_SIZE_PT, CUTOUT_SIZE_PT)
            )
            cutout_path.fill()

            # Active indicator dot
            ctx.setCompositingOperation_(AppKit.NSCompositingOperationSourceOver)
            dot_path = AppKit.NSBezierPath.bezierPathWithOvalInRect_(
                AppKit.NSMakeRect(DOT_X_PT, DOT_Y_PT, DOT_SIZE_PT, DOT_SIZE_PT)
            )
            dot_color = AppKit.NSColor.colorWithCalibratedRed_green_blue_alpha_(
                DOT_COLOR_RGB[0] / 255.0,
                DOT_COLOR_RGB[1] / 255.0,
                DOT_COLOR_RGB[2] / 255.0,
                1.0,
            )
            dot_color.set()
            dot_path.fill()
    finally:
        AppKit.NSGraphicsContext.restoreGraphicsState()

    png_data = rep.representationUsingType_properties_(AppKit.NSPNGFileType, None)
    return bytes(png_data)


def _render_icon_pillow(state: str, pixels_wide: int, pixels_high: int) -> bytes:
    """
    Fallback renderer using Pillow supersampling in case AppKit is unavailable.
    """
    import io
    from PIL import Image, ImageDraw

    # Use 8x supersampling for smooth anti-aliased curves
    scale = 8 * (pixels_wide // 22)
    s_w = int(CANVAS_POINTS * scale)
    s_h = int(CANVAS_POINTS * scale)

    img = Image.new("RGBA", (s_w, s_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    alpha_val = int(255 * PAUSED_ALPHA) if state == "paused" else 255
    clyde_color = (255, 255, 255, alpha_val)

    cx0 = int(CLYDE_X_PT * scale)
    cy0 = int((CANVAS_POINTS - (CLYDE_Y_PT + CLYDE_H_PT)) * scale)
    cw = int(CLYDE_W_PT * scale)
    ch = int(CLYDE_H_PT * scale)
    draw.rounded_rectangle([cx0, cy0, cx0 + cw, cy0 + ch], radius=int(cw * 0.25), fill=clyde_color)

    # Eyes
    eye_r = int(cw * 0.12)
    e1_x = int(cx0 + cw * 0.35)
    e2_x = int(cx0 + cw * 0.65)
    e_y = int(cy0 + ch * 0.45)
    draw.ellipse([e1_x - eye_r, e_y - eye_r, e1_x + eye_r, e_y + eye_r], fill=(0, 0, 0, 0))
    draw.ellipse([e2_x - eye_r, e_y - eye_r, e2_x + eye_r, e_y + eye_r], fill=(0, 0, 0, 0))

    if state == "active":
        cut_x0 = int(CUTOUT_X_PT * scale)
        cut_y0 = int((CANVAS_POINTS - (CUTOUT_Y_PT + CUTOUT_SIZE_PT)) * scale)
        cut_s = int(CUTOUT_SIZE_PT * scale)
        draw.ellipse([cut_x0, cut_y0, cut_x0 + cut_s, cut_y0 + cut_s], fill=(0, 0, 0, 0))

        dot_x0 = int(DOT_X_PT * scale)
        dot_y0 = int((CANVAS_POINTS - (DOT_Y_PT + DOT_SIZE_PT)) * scale)
        dot_s = int(DOT_SIZE_PT * scale)
        dot_rgba = (DOT_COLOR_RGB[0], DOT_COLOR_RGB[1], DOT_COLOR_RGB[2], 255)
        draw.ellipse([dot_x0, dot_y0, dot_x0 + dot_s, dot_y0 + dot_s], fill=dot_rgba)

    resample_filter = getattr(Image, "Resampling", Image).LANCZOS
    final_img = img.resize((pixels_wide, pixels_high), resample=resample_filter)
    buf = io.BytesIO()
    final_img.save(buf, format="PNG")
    return buf.getvalue()


def render_icon_bytes(state: str, width_px: int, height_px: int) -> bytes:
    """
    Renders icon PNG bytes for a given state ('normal', 'active', 'paused')
    and pixel resolution (e.g. 22x22 or 44x44).
    Prefers Cocoa/AppKit CoreGraphics and falls back to Pillow if needed.
    """
    state_norm = state.lower().strip()
    if state_norm not in ("normal", "active", "paused"):
        raise ValueError(f"Invalid state '{state}'. Expected 'normal', 'active', or 'paused'.")

    try:
        import AppKit
        return _render_icon_cocoa(state_norm, width_px, height_px)
    except Exception:
        return _render_icon_pillow(state_norm, width_px, height_px)


def generate_status_icons(output_dir: Optional[str] = None) -> Dict[str, str]:
    """
    Generates all status bar icons (1x and 2x) in the specified output directory.

    Args:
        output_dir: Directory where PNG files will be written. If None, defaults to
                    the 'assets' subfolder relative to this module.

    Returns:
        Dict[str, str] mapping state names to absolute paths:
          - 'normal', 'normal@2x', 'normal_2x', 'normal_1x'
          - 'active', 'active@2x', 'active_2x', 'active_1x'
          - 'paused', 'paused@2x', 'paused_2x', 'paused_1x'
    """
    if not output_dir:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        output_dir = os.path.join(base_dir, "assets")

    output_dir = os.path.abspath(output_dir)
    os.makedirs(output_dir, exist_ok=True)

    result: Dict[str, str] = {}
    states = ["normal", "active", "paused"]

    for state in states:
        # Standard 1x: 22x22 px
        filename_1x = f"menubar_{state}.png"
        path_1x = os.path.join(output_dir, filename_1x)
        data_1x = render_icon_bytes(state, 22, 22)
        with open(path_1x, "wb") as f:
            f.write(data_1x)

        # Retina 2x: 44x44 px
        filename_2x = f"menubar_{state}@2x.png"
        path_2x = os.path.join(output_dir, filename_2x)
        data_2x = render_icon_bytes(state, 44, 44)
        with open(path_2x, "wb") as f:
            f.write(data_2x)

        # Populate contract keys
        result[state] = path_1x
        result[f"{state}@2x"] = path_2x
        result[f"{state}_2x"] = path_2x
        result[f"{state}_1x"] = path_1x

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Generate dynamic macOS status bar icons for Discord RPC (Normal, Active, Paused)."
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets"),
        help="Directory to save the generated icons (default: ./assets)",
    )
    args = parser.parse_args()

    icons = generate_status_icons(args.output_dir)
    print(f"Generated status icons successfully in: {args.output_dir}")
    for state in ["normal", "active", "paused"]:
        print(f"  {state:<12s} (1x): {icons[state]}")
        print(f"  {state + '@2x':<12s} (2x): {icons[state + '@2x']}")


if __name__ == "__main__":
    main()
