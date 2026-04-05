from __future__ import annotations

from math import cos, radians, sin
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter


ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "static" / "icon" / "variants"
MASTER_SIZE = 1024
PREVIEW_SIZE = 256


VARIANTS = [
    {
        "name": "glacier",
        "label": "Glacier Lab",
        "bg_top": "#081a24",
        "bg_bottom": "#071015",
        "glow_a": "#14d8ff66",
        "glow_b": "#b7ff6a33",
        "frame": "#67e8f93f",
        "letter_left": "#f4fffb",
        "letter_right": "#cbf7ff",
        "cross": "#effdff",
        "core": "#b7ff6a",
        "ring": "#67e8f955",
        "orbit": "#67e8f9",
        "orbit_node": "#b7ff6a",
        "grid": "#ffffff10",
        "tick": "#67e8f936",
        "style": "orbit",
    },
    {
        "name": "graphite",
        "label": "Graphite Core",
        "bg_top": "#101419",
        "bg_bottom": "#0a0d10",
        "glow_a": "#7dd3fc30",
        "glow_b": "#dce7ef18",
        "frame": "#cbd5e124",
        "letter_left": "#ffffff",
        "letter_right": "#d8e1e8",
        "cross": "#ffffff",
        "core": "#7dd3fc",
        "ring": "#dbeafe33",
        "orbit": "#93c5fd",
        "orbit_node": "#e5e7eb",
        "grid": "#ffffff0c",
        "tick": "#dbeafe2a",
        "style": "minimal",
    },
    {
        "name": "terminal",
        "label": "Terminal Green",
        "bg_top": "#04110b",
        "bg_bottom": "#020806",
        "glow_a": "#34d39944",
        "glow_b": "#bef26422",
        "frame": "#86efac2c",
        "letter_left": "#efffed",
        "letter_right": "#d8ffe0",
        "cross": "#f4fff4",
        "core": "#bef264",
        "ring": "#86efac42",
        "orbit": "#4ade80",
        "orbit_node": "#bef264",
        "grid": "#b7f7cf10",
        "tick": "#86efac30",
        "style": "terminal",
    },
    {
        "name": "signal",
        "label": "Signal Deck",
        "bg_top": "#0f1628",
        "bg_bottom": "#081015",
        "glow_a": "#38bdf844",
        "glow_b": "#fb923c2a",
        "frame": "#7dd3fc2e",
        "letter_left": "#fff8ed",
        "letter_right": "#d7efff",
        "cross": "#fff4d6",
        "core": "#fbbf24",
        "ring": "#7dd3fc48",
        "orbit": "#38bdf8",
        "orbit_node": "#fbbf24",
        "grid": "#ffffff10",
        "tick": "#fb923c28",
        "style": "signal",
    },
]


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


def _draw_grid(size: int, color: str) -> Image.Image:
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    spacing = 68
    grid_color = _hex(color)
    for x in range(0, size, spacing):
        draw.line((x, 0, x, size), fill=grid_color, width=1)
    for y in range(0, size, spacing):
        draw.line((0, y, size, y), fill=grid_color, width=1)
    return layer


def _draw_a_mark(size: int, palette: dict) -> Image.Image:
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    draw.line((304, 790, 512, 238), fill=_hex(palette["letter_left"]), width=88, joint="curve")
    draw.line((720, 790, 512, 238), fill=_hex(palette["letter_right"]), width=88, joint="curve")
    draw.line((398, 560, 626, 560), fill=_hex(palette["cross"]), width=64, joint="curve")
    return layer


def _draw_orbit(size: int, palette: dict, style: str) -> Image.Image:
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    orbit_color = _hex(palette["orbit"])
    node_color = _hex(palette["orbit_node"])

    if style == "minimal":
        draw.arc((596, 184, 842, 430), start=228, end=12, fill=orbit_color, width=16)
        draw.ellipse((760, 378, 822, 440), fill=node_color)
        return layer

    if style == "terminal":
        draw.arc((548, 138, 900, 490), start=205, end=12, fill=orbit_color, width=18)
        draw.ellipse((790, 426, 846, 482), fill=node_color)
        draw.line((146, 804, 286, 804), fill=_hex(palette["tick"]), width=10)
        draw.line((170, 830, 268, 830), fill=_hex(palette["tick"]), width=6)
        return layer

    if style == "signal":
        draw.arc((536, 148, 892, 504), start=214, end=30, fill=orbit_color, width=24)
        draw.arc((576, 188, 852, 464), start=216, end=346, fill=_hex("#ffffff18"), width=6)
        draw.ellipse((786, 438, 850, 502), fill=node_color)
        draw.ellipse((652, 158, 706, 212), fill=orbit_color)
        return layer

    draw.arc((540, 150, 888, 498), start=212, end=28, fill=orbit_color, width=22)
    draw.ellipse((772, 430, 846, 504), fill=node_color)
    draw.ellipse((654, 162, 706, 214), fill=orbit_color)
    return layer


def _draw_core(size: int, palette: dict, style: str) -> Image.Image:
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    core_color = _hex(palette["core"])
    ring_color = _hex(palette["ring"])
    if style == "minimal":
        draw.ellipse((470, 470, 554, 554), fill=core_color)
        draw.ellipse((434, 434, 590, 590), outline=ring_color, width=8)
        return layer
    draw.ellipse((464, 464, 560, 560), fill=core_color)
    draw.ellipse((430, 430, 594, 594), outline=ring_color, width=10)
    return layer


def _draw_frame(size: int, palette: dict) -> Image.Image:
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    draw.rounded_rectangle((42, 42, size - 43, size - 43), radius=278, outline=_hex(palette["frame"]), width=8)
    draw.rounded_rectangle((80, 80, size - 81, size - 81), radius=238, outline=_hex("#ffffff14"), width=4)
    return layer


def _draw_ticks(size: int, palette: dict, style: str) -> Image.Image:
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    tick_color = _hex(palette["tick"])
    draw.line((142, 324, 268, 324), fill=tick_color, width=8)
    draw.line((742, 884, 886, 884), fill=tick_color, width=8)
    if style in {"glacier", "orbit"}:
        draw.line((136, 770, 302, 770), fill=tick_color, width=8)
    if style == "signal":
        draw.line((130, 770, 224, 770), fill=tick_color, width=8)
        draw.line((130, 796, 280, 796), fill=tick_color, width=8)
    for angle in (24, 58, 112):
        r = 364
        x = 512 + r * cos(radians(angle))
        y = 512 - r * sin(radians(angle))
        draw.line((x - 20, y, x + 20, y), fill=_hex("#ffffff16"), width=4)
    return layer


def build_variant(palette: dict) -> Image.Image:
    size = MASTER_SIZE
    background = _vertical_gradient(size, palette["bg_top"], palette["bg_bottom"])
    background = Image.alpha_composite(background, _radial_glow(size, (size * 0.22, size * 0.18), size * 0.54, palette["glow_a"]))
    background = Image.alpha_composite(background, _radial_glow(size, (size * 0.82, size * 0.2), size * 0.34, palette["glow_b"]))
    background = Image.alpha_composite(background, _radial_glow(size, (size * 0.76, size * 0.84), size * 0.42, palette["glow_a"]))
    background = Image.alpha_composite(background, _draw_grid(size, palette["grid"]))
    background = Image.alpha_composite(background, _draw_frame(size, palette))

    a_mark = _draw_a_mark(size, palette)
    glow = a_mark.filter(ImageFilter.GaussianBlur(24))
    glow_tint = Image.new("RGBA", (size, size), _hex(palette["orbit"]))
    background = Image.alpha_composite(background, ImageChops.multiply(glow, glow_tint))
    background = Image.alpha_composite(background, a_mark)

    orbit = _draw_orbit(size, palette, palette["style"])
    orbit_glow = orbit.filter(ImageFilter.GaussianBlur(10))
    orbit_tint = Image.new("RGBA", (size, size), _hex(palette["orbit"]))
    background = Image.alpha_composite(background, ImageChops.multiply(orbit_glow, orbit_tint))
    background = Image.alpha_composite(background, orbit)

    core = _draw_core(size, palette, palette["style"])
    core_glow = core.filter(ImageFilter.GaussianBlur(18))
    core_tint = Image.new("RGBA", (size, size), _hex(palette["core"]))
    background = Image.alpha_composite(background, ImageChops.multiply(core_glow, core_tint))
    background = Image.alpha_composite(background, core)
    background = Image.alpha_composite(background, _draw_ticks(size, palette, palette["style"]))

    final = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    final.paste(background, (0, 0), _rounded_mask(size, 272))
    return final


def build_sheet(previews: list[tuple[str, Image.Image]]) -> Image.Image:
    card_w = 340
    card_h = 390
    cols = 2
    rows = 2
    canvas = Image.new("RGBA", (card_w * cols + 36, card_h * rows + 36), _hex("#071015"))
    draw = ImageDraw.Draw(canvas)

    try:
        from PIL import ImageFont

        title_font = ImageFont.truetype("C:/Windows/Fonts/seguisb.ttf", 28)
        body_font = ImageFont.truetype("C:/Windows/Fonts/consola.ttf", 20)
    except Exception:
        title_font = None
        body_font = None

    for index, (label, image) in enumerate(previews):
        col = index % cols
        row = index // cols
        x = 18 + col * card_w
        y = 18 + row * card_h
        draw.rounded_rectangle((x, y, x + card_w - 18, y + card_h - 18), radius=28, fill=_hex("#0d161d"), outline=_hex("#67e8f922"), width=2)
        preview = image.resize((256, 256), Image.Resampling.LANCZOS)
        canvas.alpha_composite(preview, (x + 32, y + 30))
        text_x = x + 28
        text_y = y + 304
        draw.text((text_x, text_y), label, fill=_hex("#eff8fb"), font=title_font)
        draw.text((text_x, text_y + 42), f"variant::{label.lower().replace(' ', '_')}", fill=_hex("#8ca3ad"), font=body_font)
    return canvas


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    previews: list[tuple[str, Image.Image]] = []
    for variant in VARIANTS:
        master = build_variant(variant)
        preview = master.resize((PREVIEW_SIZE, PREVIEW_SIZE), Image.Resampling.LANCZOS)
        preview.save(OUT_DIR / f"{variant['name']}.png")
        previews.append((variant["label"], master))
    sheet = build_sheet(previews)
    sheet.save(OUT_DIR / "aaroncore-variants-overview.png")
    print(f"Generated {len(VARIANTS)} AaronCore icon variants in {OUT_DIR}")


if __name__ == "__main__":
    main()
