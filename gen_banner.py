"""Generates a custom banner illustration (gradient sky + government-building
silhouette + tricolor accent) for the Dashboard hero section. Custom-drawn, not a
photo, so there's no copyright concern using it in the app."""
from PIL import Image, ImageDraw
import math
import os

W, H = 1600, 260
NAVY = (27, 42, 74)
NAVY2 = (16, 26, 48)
BLUE = (0, 119, 182)
SAFFRON = (255, 153, 51)
GREEN = (19, 136, 8)
WHITE = (255, 255, 255)

img = Image.new("RGB", (W, H), NAVY)
draw = ImageDraw.Draw(img)

# vertical gradient navy -> slightly lighter navy
for y in range(H):
    t = y / H
    r = int(NAVY[0] + (BLUE[0] - NAVY[0]) * 0.15 * t)
    g = int(NAVY[1] + (BLUE[1] - NAVY[1]) * 0.15 * t)
    b = int(NAVY[2] + (BLUE[2] - NAVY[2]) * 0.15 * t)
    draw.line([(0, y), (W, y)], fill=(r, g, b))

# soft radial glow behind left text area (draw before silhouette/stripes so it
# doesn't wash out their colors)
glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
gdraw = ImageDraw.Draw(glow)
gdraw.ellipse([-200, -150, 500, 400], fill=(0, 119, 182, 50))
img = Image.alpha_composite(img.convert("RGBA"), glow).convert("RGB")
draw = ImageDraw.Draw(img)

# building silhouette (parliament-style dome + colonnade), right-aligned
base_y = H - 40
bx0, bx1 = W - 780, W - 60
draw.rectangle([bx0, base_y - 70, bx1, base_y], fill=NAVY2)
n_cols = 22
col_w = (bx1 - bx0) / n_cols
for i in range(n_cols):
    cx = bx0 + i * col_w + col_w * 0.3
    draw.rectangle([cx, base_y - 65, cx + col_w * 0.4, base_y - 5], fill=(10, 16, 30))
# central dome
dome_cx = (bx0 + bx1) / 2
draw.pieslice([dome_cx - 90, base_y - 160, dome_cx + 90, base_y - 20], 180, 360, fill=NAVY2)
draw.rectangle([dome_cx - 95, base_y - 75, dome_cx + 95, base_y - 65], fill=NAVY2)
draw.rectangle([dome_cx - 6, base_y - 190, dome_cx + 6, base_y - 158], fill=NAVY2)
draw.ellipse([dome_cx - 10, base_y - 200, dome_cx + 10, base_y - 182], fill=NAVY2)

# tricolor accent stripe at very bottom (saffron / white / green, top to bottom)
stripe_h = 6
draw.rectangle([0, H - stripe_h * 3, W, H - stripe_h * 2], fill=SAFFRON)
draw.rectangle([0, H - stripe_h * 2, W, H - stripe_h], fill=WHITE)
draw.rectangle([0, H - stripe_h, W, H], fill=GREEN)

out_dir = os.path.join(os.path.dirname(__file__), "assets")
os.makedirs(out_dir, exist_ok=True)
img.save(os.path.join(out_dir, "hero_banner.png"))
print("Saved assets/hero_banner.png")
