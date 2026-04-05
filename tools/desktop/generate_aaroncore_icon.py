from __future__ import annotations

from math import cos, radians, sin
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter


ROOT = Path(__file__).resolve().parents[2]
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
            px[x, y] = rgba[0], rgba[1], rgba[2], int(rgba[3] * alpha)
    return image


def _rounded_mask(size: int, radius: int) -> Image.Image:
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=radius, fill=255)
    return mask


def _draw_grid(size: int) -> Image.Image:
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    spacing = 68
    color = _hex("#ffffff10")
    for x in range(0, size, spacing):
        draw.line((x, 0, x, size), fill=color, width=1)
    for y in range(0, size, spacing):
        draw.line((0, y, size, y), fill=color, width=1)
    return layer


def _draw_a_mark(size: int) -> Image.Image:
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    draw.line((304, 790, 512, 238), fill=_hex("#f4fffb"), width=88, joint="curve")
    draw.line((720, 790, 512, 238), fill=_hex("#c4f8ff"), width=88, joint="curve")
    draw.line((398, 560, 626, 560), fill=_hex("#ecfdff"), width=64, joint="curve")
    return layer


def _draw_orbit(size: int) -> Image.Image:
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    draw.arc((540, 150, 888, 498), start=212, end=28, fill=_hex("#67e8f9"), width=22)
    draw.ellipse((772, 430, 846, 504), fill=_hex("#b7ff6a"))
    draw.ellipse((654, 162, 706, 214), fill=_hex("#67e8f9"))
    return layer


def _draw_core(size: int) -> Image.Image:
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    draw.ellipse((464, 464, 560, 560), fill=_hex("#b7ff6a"))
    draw.ellipse((430, 430, 594, 594), outline=_hex("#67e8f955"), width=10)
    return layer


def _draw_trace_ticks(size: int) -> Image.Image:
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    draw.line((142, 324, 268, 324), fill=_hex("#67e8f936"), width=8)
    draw.line((136, 770, 302, 770), fill=_hex("#67e8f924"), width=8)
    draw.line((742, 884, 886, 884), fill=_hex("#b7ff6a33"), width=8)
    for angle in (24, 58, 112):
        r = 364
        x = 512 + r * cos(radians(angle))
        y = 512 - r * sin(radians(angle))
        draw.line((x - 20, y, x + 20, y), fill=_hex("#ffffff16"), width=4)
    return layer


def build_master_icon() -> Image.Image:
    size = MASTER_SIZE
    background = _vertical_gradient(size, "#0a1822", "#071015")
    background = Image.alpha_composite(background, _radial_glow(size, (size * 0.22, size * 0.18), size * 0.54, "#13d7ff66"))
    background = Image.alpha_composite(background, _radial_glow(size, (size * 0.82, size * 0.2), size * 0.34, "#b7ff6a33"))
    background = Image.alpha_composite(background, _radial_glow(size, (size * 0.76, size * 0.84), size * 0.42, "#0ea5e944"))
    background = Image.alpha_composite(background, _draw_grid(size))

    frame = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    frame_draw = ImageDraw.Draw(frame)
    frame_draw.rounded_rectangle((42, 42, size - 43, size - 43), radius=278, outline=_hex("#67e8f93a"), width=8)
    frame_draw.rounded_rectangle((80, 80, size - 81, size - 81), radius=238, outline=_hex("#ffffff14"), width=4)
    background = Image.alpha_composite(background, frame)

    glow = _draw_a_mark(size).filter(ImageFilter.GaussianBlur(24))
    glow_tint = Image.new("RGBA", (size, size), _hex("#22d3ee"))
    background = Image.alpha_composite(background, ImageChops.multiply(glow, glow_tint))
    background = Image.alpha_composite(background, _draw_a_mark(size))

    orbit_glow = _draw_orbit(size).filter(ImageFilter.GaussianBlur(10))
    orbit_tint = Image.new("RGBA", (size, size), _hex("#67e8f9bb"))
    background = Image.alpha_composite(background, ImageChops.multiply(orbit_glow, orbit_tint))
    background = Image.alpha_composite(background, _draw_orbit(size))

    core_glow = _draw_core(size).filter(ImageFilter.GaussianBlur(18))
    core_tint = Image.new("RGBA", (size, size), _hex("#b7ff6a99"))
    background = Image.alpha_composite(background, ImageChops.multiply(core_glow, core_tint))
    background = Image.alpha_composite(background, _draw_core(size))
    background = Image.alpha_composite(background, _draw_trace_ticks(size))

    final = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    final.paste(background, (0, 0), _rounded_mask(size, 272))
    return final


def save_icons(master: Image.Image, icon_dir: Path) -> None:
    icon_dir.mkdir(parents=True, exist_ok=True)
    for px in SIZES:
        resized = master.resize((px, px), Image.Resampling.LANCZOS)
        resized.save(icon_dir / f"nova_{px}.png")
    master.resize((512, 512), Image.Resampling.LANCZOS).save(icon_dir / "nova_master.png")
    master.save(icon_dir / "nova.ico", sizes=[(px, px) for px in SIZES])
    master.save(icon_dir / "nova_desktop.ico", sizes=[(px, px) for px in SIZES])


def main() -> None:
    master = build_master_icon()
    save_icons(master, ICON_DIR)
    for mirror_dir in MIRROR_DIRS:
        if mirror_dir.exists():
            save_icons(master, mirror_dir)
    print(f"Generated AaronCore icon set in {ICON_DIR}")


if __name__ == "__main__":
    main()
