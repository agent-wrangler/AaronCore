"""Legacy icon generator for NovaCore desktop assets."""

from pathlib import Path
import math

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "static" / "icon"
SIZES = [256, 128, 64, 48, 32, 16]

COLOR_TOP = (99, 102, 241)
COLOR_BOT = (139, 92, 246)


def lerp_color(c1, c2, t):
    return tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))


def make_icon(size):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    radius = size // 4
    draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=COLOR_TOP)
    for y in range(size):
        t = y / max(size - 1, 1)
        color = lerp_color(COLOR_TOP, COLOR_BOT, t)
        for x in range(size):
            if img.getpixel((x, y))[3] > 0:
                img.putpixel((x, y), (*color, 255))

    cx, cy = size / 2, size / 2
    outer = size * 0.38
    inner = size * 0.12
    points = []
    for i in range(8):
        angle = math.radians(i * 45 - 90)
        r = outer if i % 2 == 0 else inner
        points.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    draw.polygon(points, fill=(255, 255, 255, 240))

    sx, sy = cx + size * 0.22, cy - size * 0.22
    sm_outer = size * 0.08
    sm_inner = size * 0.03
    sm_points = []
    for i in range(8):
        angle = math.radians(i * 45 - 90)
        r = sm_outer if i % 2 == 0 else sm_inner
        sm_points.append((sx + r * math.cos(angle), sy + r * math.sin(angle)))
    draw.polygon(sm_points, fill=(255, 255, 255, 180))

    return img


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    images = []
    for size in SIZES:
        img = make_icon(size)
        img.save(OUT / f"nova_{size}.png")
        images.append(img)
        print(f"  nova_{size}.png")

    ico_path = OUT / "nova.ico"
    images[0].save(
        ico_path,
        format="ICO",
        sizes=[(size, size) for size in SIZES],
        append_images=images[1:],
    )
    print("  nova.ico")
    print(f"\nDone -> {OUT}")


if __name__ == "__main__":
    main()
