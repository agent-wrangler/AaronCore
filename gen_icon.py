"""生成 NovaCore 应用图标 — 紫色圆角底 + 四角星"""
from PIL import Image, ImageDraw
import math
import os

SIZES = [256, 128, 64, 48, 32, 16]
OUT = os.path.join(os.path.dirname(__file__), "static", "icon")
os.makedirs(OUT, exist_ok=True)

# 主色：跟 app accent #8b5cf6 / #6366f1 渐变
COLOR_TOP = (99, 102, 241)      # #6366f1
COLOR_BOT = (139, 92, 246)      # #8b5cf6
BG_DARK = (11, 16, 32)          # #0b1020


def lerp_color(c1, c2, t):
    return tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))


def make_icon(size):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 圆角矩形背景（渐变）
    radius = size // 4
    # 先画纯色圆角矩形，再逐行覆盖渐变
    draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=COLOR_TOP)
    # 简单垂直渐变
    for y in range(size):
        t = y / max(size - 1, 1)
        color = lerp_color(COLOR_TOP, COLOR_BOT, t)
        for x in range(size):
            if img.getpixel((x, y))[3] > 0:  # 只在圆角矩形内部画
                img.putpixel((x, y), (*color, 255))

    # 画四角星
    draw = ImageDraw.Draw(img)
    cx, cy = size / 2, size / 2
    outer = size * 0.38   # 尖端到中心
    inner = size * 0.12   # 凹陷到中心
    points = []
    for i in range(8):
        angle = math.radians(i * 45 - 90)  # 从正上方开始
        r = outer if i % 2 == 0 else inner
        points.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    draw.polygon(points, fill=(255, 255, 255, 240))

    # 加一颗小星星点缀（右上角）
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


# 生成各尺寸 PNG
images = []
for s in SIZES:
    img = make_icon(s)
    img.save(os.path.join(OUT, f"nova_{s}.png"))
    images.append(img)
    print(f"  nova_{s}.png")

# 生成 ICO（多尺寸）
ico_path = os.path.join(OUT, "nova.ico")
images[0].save(ico_path, format="ICO", sizes=[(s, s) for s in SIZES],
               append_images=images[1:])
print(f"  nova.ico")
print(f"\nDone → {OUT}")
