#!/usr/bin/env python3
"""Generate pixel art GitPup avatar as PNG.

Creates a cute golden retriever puppy in pixel art style.
Uses the Pillow library for rendering.
"""

from PIL import Image, ImageDraw

# Palette
BG = "#0f0f23"
FUR_LIGHT = "#f0c848"
FUR_MID = "#d4a030"
FUR_DARK = "#b08020"
NOSE = "#1a1a2e"
EYE = "#1a1a2e"
EYE_SHINE = "#ffffff"
TONGUE = "#f4a0a0"
CHEEK = "#f4a0a0"
TEXT = "#f0c848"

SCALE = 16  # pixels per "pixel"

# 16x16 grid → 256x256 image
GRID = [
    # 0=BG, 1=FUR_LIGHT, 2=FUR_MID, 3=FUR_DARK, 4=NOSE, 5=EYE, 6=EYE_SHINE, 7=TONGUE, 8=CHEEK
    [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
    [0,0,0,0,0,0,3,0,0,3,0,0,0,0,0,0],  # ears top
    [0,0,0,0,0,3,1,3,3,1,3,0,0,0,0,0],
    [0,0,0,0,3,1,2,1,1,2,1,3,0,0,0,0],
    [0,0,0,0,3,1,1,1,1,1,1,3,0,0,0,0],
    [0,0,0,0,0,1,2,1,1,2,1,0,0,0,0,0],  # head top
    [0,0,0,0,1,1,1,1,1,1,1,1,0,0,0,0],
    [0,0,3,1,1,5,5,1,1,6,6,5,1,1,3,0],  # eyes
    [0,3,1,1,1,1,1,1,1,1,1,1,1,1,1,3],
    [0,3,1,1,1,1,1,1,1,1,1,1,1,1,1,3],
    [0,0,3,1,1,1,1,4,1,1,8,8,1,1,0,0],  # nose + cheeks
    [0,0,0,3,1,1,1,1,1,3,1,1,3,0,0,0],
    [0,0,0,0,3,1,1,4,1,1,1,1,3,0,0,0],
    [0,0,0,0,0,3,1,1,1,7,7,3,0,0,0,0],  # mouth + tongue
    [0,0,0,0,0,0,3,2,2,2,2,3,0,0,0,0],  # chest
    [0,0,0,0,0,0,0,3,3,3,3,0,0,0,0,0],
]

COLORS = {
    0: BG,
    1: FUR_LIGHT,
    2: FUR_MID,
    3: FUR_DARK,
    4: NOSE,
    5: EYE,
    6: EYE_SHINE,
    7: TONGUE,
    8: CHEEK,
}

def main():
    size = 16 * SCALE
    img = Image.new("RGBA", (size, size + 32), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Draw pixel grid
    for y, row in enumerate(GRID):
        for x, color_idx in enumerate(row):
            px = x * SCALE
            py = y * SCALE + 16  # offset for text space
            draw.rectangle([px, py, px + SCALE - 1, py + SCALE - 1], fill=COLORS[color_idx])

    # "GITPUP" text
    try:
        from PIL import ImageFont
        font = ImageFont.load_default()
    except Exception:
        font = None
    draw.text((16 * SCALE // 2 - 30, size + 8), "GITPUP", fill=TEXT, font=font)

    output = "assets/gitpup-pixel.png"
    img.save(output, "PNG")
    print(f"✓ Saved: {output} ({size}x{size + 32})")

if __name__ == "__main__":
    main()
