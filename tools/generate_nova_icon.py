from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
ICON_DIR = ROOT / "static" / "icon"
MIRROR_DIRS = [
    ROOT / "desktop_runtime_35" / "dist" / "win-unpacked" / "resources" / "novacore" / "static" / "icon",
]
SIZES = [16, 32, 48, 64, 128, 256]
MASTER_SIZE = 1024


def _hex(color: str) -> tuple[int, int, int, int]:
    color = color.lstrip("#")
    if len(color) == 6:
        color += "ff"
    return tuple(int(color[i : i + 2], 16) for i in range(0, 8, 2))


def _vertical_gradient(size: int, top: str, bottom: str) -> Image.Image:
    top_rgba = _hex(top)
    bottom_rgba = _hex(bottom)
    image = Image.new("RGBA", (size, size))
    px = image.load()
    for y in range(size):
        t = y / max(size - 1, 1)
        row = tuple(int(top_rgba[i] * (1 - t) + bottom_rgba[i] * t) for i in range(4))
        for x in range(size):
            px[x, y] = row
    return image


def _radial_glow(size: int, center: tuple[float, float], radius: float, color: str) -> Image.Image:
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    px = image.load()
    cx, cy = center
    rgba = _hex(color)
    for y in range(size):
        for x in range(size):
            dx = x - cx
            dy = y - cy
            dist = (dx * dx + dy * dy) ** 0.5
            if dist >= radius:
                continue
            alpha = 1.0 - (dist / radius)
            alpha = alpha * alpha
            px[x, y] = (
                rgba[0],
                rgba[1],
                rgba[2],
                int(rgba[3] * alpha),
            )
    return image


def _rounded_mask(size: int, radius: int) -> Image.Image:
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=radius, fill=255)
    return mask


def _draw_terminal_n(size: int) -> Image.Image:
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    width = 108
    left_x = 282
    right_x = 706
    top_y = 248
    bottom_y = 776

    draw.line((left_x, bottom_y, left_x, top_y), fill=_hex("#f6fbff"), width=width, joint="curve")
    draw.line((left_x, top_y, right_x, bottom_y), fill=_hex("#d7f6ff"), width=width, joint="curve")
    draw.line((right_x, bottom_y, right_x, top_y), fill=_hex("#9ce7ff"), width=width, joint="curve")

    # Add a slim inner cut to keep the mark sharper at smaller sizes.
    cut = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    cut_draw = ImageDraw.Draw(cut)
    cut_draw.line((left_x + 34, top_y + 38, right_x - 42, bottom_y - 52), fill=(0, 0, 0, 255), width=34)
    return ImageChops.subtract(layer, cut)


def _draw_star(size: int, center: tuple[int, int], outer: int, inner: int) -> Image.Image:
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    cx, cy = center
    points: list[tuple[float, float]] = []
    for idx in range(8):
        r = outer if idx % 2 == 0 else inner
        angle = (idx * 45 - 90) * 3.141592653589793 / 180
        points.append((cx + r * __import__("math").cos(angle), cy + r * __import__("math").sin(angle)))
    draw.polygon(points, fill=_hex("#ffd978"))
    return layer


def build_master_icon() -> Image.Image:
    size = MASTER_SIZE
    background = _vertical_gradient(size, "#081018", "#12243d")
    background = Image.alpha_composite(background, _radial_glow(size, (size * 0.28, size * 0.18), size * 0.62, "#1f87ff80"))
    background = Image.alpha_composite(background, _radial_glow(size, (size * 0.76, size * 0.82), size * 0.58, "#00d4ff55"))

    accent = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    accent_draw = ImageDraw.Draw(accent)
    accent_draw.rounded_rectangle((164, 168, 860, 864), radius=268, outline=_hex("#88d5ff"), width=10)
    accent_draw.arc((118, 92, 906, 872), start=210, end=315, fill=_hex("#27d3ff"), width=18)
    accent = accent.filter(ImageFilter.GaussianBlur(3))
    background = Image.alpha_composite(background, accent)

    glyph_shadow = _draw_terminal_n(size).filter(ImageFilter.GaussianBlur(20))
    shadow_tint = Image.new("RGBA", (size, size), _hex("#20a7ff"))
    glyph_shadow = ImageChops.multiply(glyph_shadow, shadow_tint)
    background = Image.alpha_composite(background, glyph_shadow)
    background = Image.alpha_composite(background, _draw_terminal_n(size))

    star_glow = _draw_star(size, (784, 280), 88, 28).filter(ImageFilter.GaussianBlur(16))
    star_glow_tint = Image.new("RGBA", (size, size), _hex("#ffc85c88"))
    background = Image.alpha_composite(background, ImageChops.multiply(star_glow, star_glow_tint))
    background = Image.alpha_composite(background, _draw_star(size, (784, 280), 72, 22))

    # Add a crisp lower-right cursor tick so it reads like a local coding tool.
    tick = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    tick_draw = ImageDraw.Draw(tick)
    tick_draw.line((698, 804, 804, 742), fill=_hex("#46ddff"), width=40, joint="curve")
    tick_draw.line((804, 742, 842, 774), fill=_hex("#46ddff"), width=40, joint="curve")
    tick = tick.filter(ImageFilter.GaussianBlur(1))
    background = Image.alpha_composite(background, tick)

    glass = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    glass_draw = ImageDraw.Draw(glass)
    glass_draw.rounded_rectangle((44, 44, size - 45, size - 45), radius=280, outline=_hex("#ffffff26"), width=6)
    glass_draw.rounded_rectangle((72, 72, size - 73, size * 0.38), radius=210, fill=_hex("#ffffff12"))
    background = Image.alpha_composite(background, glass)

    final = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    rounded_mask = _rounded_mask(size, 272)
    final.paste(background, (0, 0), rounded_mask)
    return final


def save_icons(master: Image.Image, icon_dir: Path) -> None:
    icon_dir.mkdir(parents=True, exist_ok=True)
    for px in SIZES:
        resized = master.resize((px, px), Image.Resampling.LANCZOS)
        resized.save(icon_dir / f"nova_{px}.png")
    master.resize((512, 512), Image.Resampling.LANCZOS).save(icon_dir / "nova_master.png")
    master.save(icon_dir / "nova.ico", sizes=[(px, px) for px in SIZES])


def main() -> None:
    master = build_master_icon()
    save_icons(master, ICON_DIR)
    for mirror_dir in MIRROR_DIRS:
        if mirror_dir.exists():
            save_icons(master, mirror_dir)
    print(f"Generated icon set in {ICON_DIR}")


if __name__ == "__main__":
    main()
