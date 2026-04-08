from __future__ import annotations

import re
import struct
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(r"C:\Users\36459\NovaCore")
SVG_PATH = ROOT / "website" / "official" / "assets" / "aaroncore-logo-mark-bracket.svg"
OUT_ICO = ROOT / "static" / "icon" / "nova.ico"
OUT_ICO_AARON = ROOT / "static" / "icon" / "aaroncore.ico"
OUT_ICO_DESKTOP = ROOT / "static" / "icon" / "aaroncore-desktop.ico"
OUT_ICO_DESKTOP_MATCH = ROOT / "static" / "icon" / "aaroncore-desktop-svg.ico"
OUT_SIZE_DIR = ROOT / "static" / "icon" / "ico-sizes"

SIZES = [16, 24, 32, 48, 64, 96, 128, 256]
NUM_RE = re.compile(r"[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?")
TOKEN_RE = re.compile(r"[A-Za-z]|[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?")
SVG_NS = "{http://www.w3.org/2000/svg}"


def _oversample(size: int) -> int:
    if size <= 24:
        return 12
    if size <= 48:
        return 10
    if size <= 96:
        return 6
    if size <= 128:
        return 4
    return 2


def _identity() -> tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]:
    return (
        (1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
        (0.0, 0.0, 1.0),
    )


def _matmul(
    left: tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]],
    right: tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]],
) -> tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]:
    rows = []
    for row in range(3):
        rows.append(
            tuple(
                sum(left[row][k] * right[k][col] for k in range(3))
                for col in range(3)
            )
        )
    return tuple(rows)  # type: ignore[return-value]


def _translate(tx: float, ty: float) -> tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]:
    return (
        (1.0, 0.0, tx),
        (0.0, 1.0, ty),
        (0.0, 0.0, 1.0),
    )


def _scale(sx: float, sy: float) -> tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]:
    return (
        (sx, 0.0, 0.0),
        (0.0, sy, 0.0),
        (0.0, 0.0, 1.0),
    )


def _apply(matrix: tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]], point: tuple[float, float]) -> tuple[float, float]:
    x, y = point
    return (
        matrix[0][0] * x + matrix[0][1] * y + matrix[0][2],
        matrix[1][0] * x + matrix[1][1] * y + matrix[1][2],
    )


def _transform_scale(matrix: tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]) -> float:
    # Uniform scale is enough for this icon pipeline.
    return (matrix[0][0] ** 2 + matrix[1][0] ** 2) ** 0.5


def _hex_to_rgba(value: str, opacity: float = 1.0) -> tuple[int, int, int, int]:
    color = value.lstrip("#")
    if len(color) == 3:
        color = "".join(part * 2 for part in color)
    r = int(color[0:2], 16)
    g = int(color[2:4], 16)
    b = int(color[4:6], 16)
    a = max(0, min(255, int(round(255 * opacity))))
    return r, g, b, a


def _parse_transform(value: str | None) -> tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]:
    matrix = _identity()
    if not value:
        return matrix
    for name, args_text in re.findall(r"([A-Za-z]+)\(([^)]*)\)", value):
        values = [float(item) for item in NUM_RE.findall(args_text)]
        if name == "translate":
            tx = values[0]
            ty = values[1] if len(values) > 1 else 0.0
            matrix = _matmul(matrix, _translate(tx, ty))
        elif name == "scale":
            sx = values[0]
            sy = values[1] if len(values) > 1 else sx
            matrix = _matmul(matrix, _scale(sx, sy))
    return matrix


def _sample_cubic(
    start: tuple[float, float],
    c1: tuple[float, float],
    c2: tuple[float, float],
    end: tuple[float, float],
    steps: int = 48,
) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for index in range(1, steps + 1):
        t = index / steps
        mt = 1.0 - t
        x = (
            (mt * mt * mt * start[0])
            + (3 * mt * mt * t * c1[0])
            + (3 * mt * t * t * c2[0])
            + (t * t * t * end[0])
        )
        y = (
            (mt * mt * mt * start[1])
            + (3 * mt * mt * t * c1[1])
            + (3 * mt * t * t * c2[1])
            + (t * t * t * end[1])
        )
        points.append((x, y))
    return points


def _parse_path_points(path_d: str) -> list[tuple[float, float]]:
    tokens = TOKEN_RE.findall(path_d)
    points: list[tuple[float, float]] = []
    current = (0.0, 0.0)
    current_cmd = ""
    idx = 0
    while idx < len(tokens):
        token = tokens[idx]
        if token.isalpha():
            current_cmd = token
            idx += 1
        cmd = current_cmd
        if cmd == "M":
            current = (float(tokens[idx]), float(tokens[idx + 1]))
            points.append(current)
            idx += 2
        elif cmd == "L":
            current = (float(tokens[idx]), float(tokens[idx + 1]))
            points.append(current)
            idx += 2
        elif cmd == "H":
            current = (float(tokens[idx]), current[1])
            points.append(current)
            idx += 1
        elif cmd == "V":
            current = (current[0], float(tokens[idx]))
            points.append(current)
            idx += 1
        elif cmd == "C":
            c1 = (float(tokens[idx]), float(tokens[idx + 1]))
            c2 = (float(tokens[idx + 2]), float(tokens[idx + 3]))
            end = (float(tokens[idx + 4]), float(tokens[idx + 5]))
            points.extend(_sample_cubic(current, c1, c2, end))
            current = end
            idx += 6
        elif cmd == "Z":
            idx += 0
            break
        else:
            raise ValueError(f"Unsupported SVG path command: {cmd}")
    return points


def _draw_polyline(
    draw: ImageDraw.ImageDraw,
    points: list[tuple[float, float]],
    rgba: tuple[int, int, int, int],
    width: int,
) -> None:
    radius = width / 2.0
    for start, end in zip(points, points[1:]):
        draw.line((start, end), fill=rgba, width=width)
    for x, y in points:
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=rgba)


def _load_svg_spec() -> dict[str, object]:
    root = ET.fromstring(SVG_PATH.read_text(encoding="utf-8"))
    view_box = [float(item) for item in root.attrib["viewBox"].split()]
    canvas = view_box[2]

    rect = root.find(f"{SVG_NS}rect")
    group = root.find(f"{SVG_NS}g")
    circle = root.find(f"{SVG_NS}circle")
    if rect is None or group is None or circle is None:
        raise ValueError("Expected rect, g, and circle elements in SVG")

    group_matrix = _parse_transform(group.attrib.get("transform"))
    group_scale = _transform_scale(group_matrix)

    paths = []
    for path in group.findall(f"{SVG_NS}path"):
        points = [_apply(group_matrix, point) for point in _parse_path_points(path.attrib["d"])]
        opacity = float(path.attrib.get("stroke-opacity", "1"))
        stroke_width = float(path.attrib["stroke-width"]) * group_scale
        color = _hex_to_rgba(path.attrib["stroke"], opacity)
        paths.append(
            {
                "points": points,
                "stroke_width": stroke_width,
                "color": color,
            }
        )

    return {
        "canvas": canvas,
        "background_fill": rect.attrib["fill"],
        "background_radius": float(rect.attrib.get("rx", "0")),
        "paths": paths,
        "circle_center": (float(circle.attrib["cx"]), float(circle.attrib["cy"])),
        "circle_radius": float(circle.attrib["r"]),
        "circle_fill": circle.attrib["fill"],
    }


def _render_icon(size: int, spec: dict[str, object]) -> Image.Image:
    oversample = _oversample(size)
    render_size = size * oversample
    canvas = float(spec["canvas"])
    img = Image.new("RGBA", (render_size, render_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    draw.rounded_rectangle(
        (0, 0, render_size - 1, render_size - 1),
        radius=float(spec["background_radius"]) * render_size / canvas,
        fill=str(spec["background_fill"]),
    )

    for path in spec["paths"]:  # type: ignore[index]
        scaled = [
            (point[0] * render_size / canvas, point[1] * render_size / canvas)
            for point in path["points"]  # type: ignore[index]
        ]
        width = max(1, int(round(float(path["stroke_width"]) * render_size / canvas)))  # type: ignore[index]
        _draw_polyline(draw, scaled, path["color"], width)  # type: ignore[index]

    cx, cy = spec["circle_center"]  # type: ignore[misc]
    radius = float(spec["circle_radius"]) * render_size / canvas
    cx = cx * render_size / canvas
    cy = cy * render_size / canvas
    draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=str(spec["circle_fill"]))

    if render_size != size:
        img = img.resize((size, size), Image.Resampling.LANCZOS)

    if size <= 32:
        img = img.filter(ImageFilter.UnsharpMask(radius=0.45, percent=55, threshold=2))
    elif size <= 48:
        img = img.filter(ImageFilter.UnsharpMask(radius=0.35, percent=35, threshold=2))

    return img


def _save_ico(path: Path, spec: dict[str, object]) -> None:
    images = [_render_icon(size, spec) for size in SIZES]
    base = images[-1]
    base.save(path, format="ICO", sizes=[(size, size) for size in SIZES], append_images=images[:-1])
    _reorder_ico_directory(path)


def _save_single_size_icons(directory: Path, spec: dict[str, object]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for size in SIZES:
        image = _render_icon(size, spec)
        ico_path = directory / f"aaroncore-{size}.ico"
        png_path = directory / f"aaroncore-{size}.png"
        image.save(ico_path, format="ICO", sizes=[(size, size)])
        image.save(png_path, format="PNG")

    multi_path = directory / "aaroncore-desktop-multi.ico"
    _save_ico(multi_path, spec)


def _reorder_ico_directory(path: Path) -> None:
    data = bytearray(path.read_bytes())
    reserved, icon_type, count = struct.unpack_from("<HHH", data, 0)
    if reserved != 0 or icon_type != 1 or count <= 1:
        return

    entries = []
    offset = 6
    for index in range(count):
        entry = data[offset + index * 16 : offset + (index + 1) * 16]
        width = entry[0] or 256
        height = entry[1] or 256
        area = width * height
        entries.append((area, width, height, bytes(entry)))

    entries.sort(reverse=True)
    for index, (_, _, _, entry) in enumerate(entries):
        data[offset + index * 16 : offset + (index + 1) * 16] = entry

    path.write_bytes(data)


def main() -> None:
    spec = _load_svg_spec()
    OUT_ICO.parent.mkdir(parents=True, exist_ok=True)
    _save_ico(OUT_ICO, spec)
    _save_ico(OUT_ICO_AARON, spec)
    _save_ico(OUT_ICO_DESKTOP, spec)
    _save_ico(OUT_ICO_DESKTOP_MATCH, spec)
    _save_single_size_icons(OUT_SIZE_DIR, spec)
    print(f"Wrote {OUT_ICO}")
    print(f"Wrote {OUT_ICO_AARON}")
    print(f"Wrote {OUT_ICO_DESKTOP}")
    print(f"Wrote {OUT_ICO_DESKTOP_MATCH}")
    print(f"Wrote {OUT_SIZE_DIR}")


if __name__ == "__main__":
    main()
