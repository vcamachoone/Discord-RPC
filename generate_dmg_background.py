#!/usr/bin/env python3
"""
generate_dmg_background.py - Generates a modern dark-themed Retina background
image for the League of Legends RPC macOS DMG Installer.
"""

import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter

def get_font(size: int, bold: bool = False):
    """Finds the best available system font on macOS."""
    candidates = []
    if bold:
        candidates = [
            "/System/Library/Fonts/SFNS.ttf",
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            "/Library/Fonts/Arial Bold.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
        ]
    else:
        candidates = [
            "/System/Library/Fonts/SFNS.ttf",
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/Library/Fonts/Arial.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
        ]
    
    for path in candidates:
        if os.path.isfile(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()

def draw_rounded_rect(draw, bbox, radius, fill, outline=None, width=1):
    """Draws a smooth rounded rectangle."""
    x0, y0, x1, y1 = bbox
    draw.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=fill, outline=outline, width=width)

def generate_background(output_path: str = "dist/dmg_background.png", width: int = 1320, height: int = 840):
    """
    Generates a Retina 2x background image (1320x840 px, representing 660x420 pt).
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    
    # 1. Base Dark Canvas
    img = Image.new("RGBA", (width, height), (11, 14, 21, 255))
    draw = ImageDraw.Draw(img)

    # 2. Subtle Gradient Background
    for y in range(height):
        ratio = y / height
        # Gradient from #0d111a to #080a10
        r = int(14 * (1 - ratio) + 8 * ratio)
        g = int(18 * (1 - ratio) + 11 * ratio)
        b = int(28 * (1 - ratio) + 18 * ratio)
        draw.line([(0, y), (width, y)], fill=(r, g, b, 255))

    # 3. Soft Ambient Glows (Blurple on left, Hextech Gold on right)
    glow_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow_layer)
    
    # Discord Blurple glow on left target
    glow_draw.ellipse([80, 220, 480, 620], fill=(88, 101, 242, 35))
    # Gold glow on right target
    glow_draw.ellipse([840, 220, 1240, 620], fill=(200, 170, 110, 25))
    # Top center glow
    glow_draw.ellipse([460, -100, 860, 250], fill=(88, 101, 242, 22))

    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius=60))
    img = Image.alpha_composite(img, glow_layer)
    draw = ImageDraw.Draw(img)

    # 4. Top Accent Line (Hextech Gold & Discord Blurple gradient)
    for x in range(width):
        t = x / width
        # Transition from Gold (200, 170, 110) to Blurple (88, 101, 242) to Gold
        if t < 0.5:
            mix = t * 2
            lr = int(200 * (1 - mix) + 88 * mix)
            lg = int(170 * (1 - mix) + 101 * mix)
            lb = int(110 * (1 - mix) + 242 * mix)
        else:
            mix = (t - 0.5) * 2
            lr = int(88 * (1 - mix) + 200 * mix)
            lg = int(101 * (1 - mix) + 170 * mix)
            lb = int(242 * (1 - mix) + 110 * mix)
        draw.line([(x, 0), (x, 3)], fill=(lr, lg, lb, 220))

    # 5. Header Typography
    title_font = get_font(44, bold=True)
    subtitle_font = get_font(22, bold=False)
    badge_font = get_font(18, bold=True)
    label_font = get_font(20, bold=True)
    small_font = get_font(18, bold=False)
    arrow_label_font = get_font(22, bold=True)

    # App Title
    title_text = "LEAGUE OF LEGENDS RPC"
    bbox = draw.textbbox((0, 0), title_text, font=title_font)
    title_w = bbox[2] - bbox[0]
    draw.text(((width - title_w) // 2, 50), title_text, font=title_font, fill=(245, 247, 250, 255))

    # Subtitle
    sub_text = "Discord Rich Presence • Selector Top 10 Juegos • macOS Menubar"
    bbox_sub = draw.textbbox((0, 0), sub_text, font=subtitle_font)
    sub_w = bbox_sub[2] - bbox_sub[0]
    draw.text(((width - sub_w) // 2, 108), sub_text, font=subtitle_font, fill=(158, 168, 188, 240))

    # 6. Drop Target Guides (Cards under where the icons will be placed)
    # Centers in 2x: Left = (330, 420), Right = (990, 420)
    card_w, card_h = 220, 220
    center_y = 420
    left_center_x = 330
    right_center_x = 990

    left_x = left_center_x - (card_w // 2)
    right_x = right_center_x - (card_w // 2)
    card_y = center_y - (card_h // 2)

    # Left Target Card (App)
    draw_rounded_rect(
        draw,
        (left_x, card_y, left_x + card_w, card_y + card_h),
        radius=32,
        fill=(20, 25, 36, 170),
        outline=(88, 101, 242, 130),
        width=2
    )

    # Right Target Card (Applications)
    draw_rounded_rect(
        draw,
        (right_x, card_y, right_x + card_w, card_y + card_h),
        radius=32,
        fill=(20, 25, 36, 170),
        outline=(200, 170, 110, 130),
        width=2
    )

    # Card Labels below
    left_label = "League of Legends RPC.app"
    bbox_ll = draw.textbbox((0, 0), left_label, font=label_font)
    draw.text((left_center_x - (bbox_ll[2] - bbox_ll[0]) // 2, card_y + card_h + 20), left_label, font=label_font, fill=(230, 235, 245, 240))

    right_label = "Carpeta Aplicaciones"
    bbox_rl = draw.textbbox((0, 0), right_label, font=label_font)
    draw.text((right_center_x - (bbox_rl[2] - bbox_rl[0]) // 2, card_y + card_h + 20), right_label, font=label_font, fill=(230, 235, 245, 240))

    # 7. Directional Arrow & Drag Instruction (Center)
    arrow_center_x = width // 2
    arrow_y = center_y

    # Pill badge for "ARRASTRAR PARA INSTALAR"
    badge_text = "ARRASTRAR PARA INSTALAR"
    badge_font_refined = get_font(18, bold=True)
    badge_bbox = draw.textbbox((0, 0), badge_text, font=badge_font_refined)
    bw = badge_bbox[2] - badge_bbox[0] + 48
    bh = badge_bbox[3] - badge_bbox[1] + 20
    bx0 = arrow_center_x - (bw // 2)
    by0 = arrow_y - 65
    draw_rounded_rect(draw, (bx0, by0, bx0 + bw, by0 + bh), radius=16, fill=(88, 101, 242, 220), outline=(140, 155, 255, 240), width=2)
    draw.text((bx0 + 24, by0 + 10), badge_text, font=badge_font_refined, fill=(255, 255, 255, 255))

    # Sleek Glowing Neon Arrow
    arrow_line_start = arrow_center_x - 110
    arrow_line_end = arrow_center_x + 90
    arrow_shaft_y = arrow_y + 25
    
    # Shadow / glow for arrow
    draw.line([(arrow_line_start, arrow_shaft_y), (arrow_line_end, arrow_shaft_y)], fill=(88, 101, 242, 100), width=10)
    draw.line([(arrow_line_start, arrow_shaft_y), (arrow_line_end, arrow_shaft_y)], fill=(0, 210, 255, 230), width=5)

    # Arrowhead
    head_points = [
        (arrow_line_end + 32, arrow_shaft_y),
        (arrow_line_end, arrow_shaft_y - 20),
        (arrow_line_end + 6, arrow_shaft_y),
        (arrow_line_end, arrow_shaft_y + 20),
    ]
    draw.polygon(head_points, fill=(0, 210, 255, 250))

    # 8. Bottom Information Footer
    footer_text = "Apple Silicon & Intel • macOS 12+ • Totalmente Autónomo sin dependencias externas"
    bbox_f = draw.textbbox((0, 0), footer_text, font=small_font)
    fw = bbox_f[2] - bbox_f[0]
    draw.text(((width - fw) // 2, height - 52), footer_text, font=small_font, fill=(120, 130, 150, 200))

    # Save 2x Retina image and downscale to 1x image
    img.save(output_path, "PNG", optimize=True)
    
    # Also save 1x version (660x420)
    img_1x = img.resize((width // 2, height // 2), Image.Resampling.LANCZOS)
    path_1x = output_path.replace(".png", "_1x.png")
    img_1x.save(path_1x, "PNG", optimize=True)
    
    print(f"DMG Background generated successfully:")
    print(f"  Retina 2x: {output_path} ({width}x{height})")
    print(f"  Standard 1x: {path_1x} ({width//2}x{height//2})")
    return output_path

if __name__ == "__main__":
    generate_background()
