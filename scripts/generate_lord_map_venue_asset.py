from __future__ import annotations

import csv
import json
import math
from pathlib import Path
import struct
import zlib


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LORD_ASSET_ROOT = PROJECT_ROOT / "backend" / "witcher_larp" / "web" / "lord" / "assets"
LAYOUT_PATH = LORD_ASSET_ROOT / "lord_map_layout.json"
MAP_NODES_PATH = PROJECT_ROOT / "data" / "seed" / "map_nodes.csv"
OUTPUT_PATH = LORD_ASSET_ROOT / "lord_map_venue_v1.png"


TERRAIN_COLORS = {
    "field": (158, 145, 82),
    "forest": (47, 89, 54),
    "fort": (128, 111, 78),
    "lake": (49, 104, 116),
    "magic_city": (94, 74, 126),
    "mountain": (129, 132, 120),
    "no_play_zone": (45, 43, 39),
    "residence": (128, 96, 60),
    "resource_city": (146, 113, 69),
    "science_city": (103, 116, 101),
    "swamp": (54, 83, 71),
    "village_barn": (129, 95, 58),
}


def main() -> None:
    layout = json.loads(LAYOUT_PATH.read_text(encoding="utf-8"))
    seed_nodes = load_seed_nodes()
    width = int(layout["canvas"]["width"])
    height = int(layout["canvas"]["height"])

    pixels = bytearray(width * height * 3)
    paint_base(pixels, width, height)
    paint_territory_washes(pixels, width, height, layout, seed_nodes)
    paint_central_house_wash(pixels, width, height, layout.get("central_house"))
    paint_border_vignette(pixels, width, height)
    write_png(OUTPUT_PATH, width, height, pixels)


def load_seed_nodes() -> dict[str, dict[str, str]]:
    with MAP_NODES_PATH.open(encoding="utf-8", newline="") as handle:
        return {row["node_id"]: row for row in csv.DictReader(handle)}


def paint_base(pixels: bytearray, width: int, height: int) -> None:
    for y in range(height):
        y_ratio = y / max(1, height - 1)
        for x in range(width):
            x_ratio = x / max(1, width - 1)
            noise = hash_noise(x // 7, y // 7)
            cloth = 1 - abs(x_ratio - 0.5) * 0.3 - abs(y_ratio - 0.52) * 0.18
            index = (y * width + x) * 3
            pixels[index] = clamp(58 + 18 * cloth + noise % 9)
            pixels[index + 1] = clamp(74 + 28 * cloth + noise % 10)
            pixels[index + 2] = clamp(50 + 12 * cloth + noise % 7)

    paint_grid(pixels, width, height)
    paint_soft_roads_field(pixels, width, height)


def paint_grid(pixels: bytearray, width: int, height: int) -> None:
    for x in range(0, width, 96):
        for y in range(height):
            blend_pixel(pixels, width, x, y, (180, 155, 92), 0.08)
    for y in range(0, height, 96):
        for x in range(width):
            blend_pixel(pixels, width, x, y, (180, 155, 92), 0.08)


def paint_soft_roads_field(pixels: bytearray, width: int, height: int) -> None:
    # The live SVG draws exact graph roads. These broad stains only make the
    # large board feel like one continuous map instead of a flat UI panel.
    for index in range(18):
        cx = 160 + hash_noise(index, 11) % max(1, width - 320)
        cy = 120 + hash_noise(index, 29) % max(1, height - 240)
        radius = 120 + hash_noise(index, 53) % 180
        color = (74, 88, 56) if index % 3 else (91, 86, 59)
        draw_disc(pixels, width, height, cx, cy, radius, color, 0.06)


def paint_territory_washes(
    pixels: bytearray,
    width: int,
    height: int,
    layout: dict,
    seed_nodes: dict[str, dict[str, str]],
) -> None:
    for node_id, node in layout["nodes"].items():
        seed = seed_nodes[node_id]
        node_type = seed["node_type"]
        color = TERRAIN_COLORS.get(node_type, (118, 104, 74))
        alpha = 0.08 if node_type == "residence" else 0.18
        if seed["zone_status"] == "no_play_excluded":
            alpha = 0.34
        fill_hit_zone(pixels, width, height, node["hit_zone"], color, alpha)
        stroke_hit_zone(pixels, width, height, node["hit_zone"], (222, 186, 105), 0.16)


def paint_central_house_wash(
    pixels: bytearray,
    width: int,
    height: int,
    central_house: dict | None,
) -> None:
    if not central_house:
        return
    x = int(central_house["x"])
    y = int(central_house["y"])
    w = int(central_house["w"])
    h = int(central_house["h"])
    draw_rect(pixels, width, height, x - 24, y - 22, w + 48, h + 44, (35, 27, 19), 0.22)
    draw_rect(pixels, width, height, x, y, w, h, (113, 84, 51), 0.34)
    draw_rect(pixels, width, height, x + 22, y + 20, w - 44, h - 40, (58, 43, 30), 0.18)


def paint_border_vignette(pixels: bytearray, width: int, height: int) -> None:
    border = 190
    for y in range(height):
        for x in range(width):
            edge = min(x, y, width - 1 - x, height - 1 - y)
            if edge >= border:
                continue
            amount = 0.32 * (1 - edge / border) ** 1.6
            index = (y * width + x) * 3
            factor = max(0.5, 1 - amount)
            pixels[index] = clamp(pixels[index] * factor)
            pixels[index + 1] = clamp(pixels[index + 1] * factor)
            pixels[index + 2] = clamp(pixels[index + 2] * factor)


def fill_hit_zone(
    pixels: bytearray,
    width: int,
    height: int,
    hit_zone: dict,
    color: tuple[int, int, int],
    alpha: float,
) -> None:
    if hit_zone["type"] == "circle":
        draw_disc(
            pixels,
            width,
            height,
            int(hit_zone["cx"]),
            int(hit_zone["cy"]),
            int(hit_zone["r"]),
            color,
            alpha,
        )
        return
    fill_polygon(
        pixels,
        width,
        height,
        [(int(x), int(y)) for x, y in hit_zone["points"]],
        color,
        alpha,
    )


def stroke_hit_zone(
    pixels: bytearray,
    width: int,
    height: int,
    hit_zone: dict,
    color: tuple[int, int, int],
    alpha: float,
) -> None:
    if hit_zone["type"] == "circle":
        cx = int(hit_zone["cx"])
        cy = int(hit_zone["cy"])
        radius = int(hit_zone["r"])
        steps = max(24, int(radius * 1.8))
        points = [
            (
                int(cx + math.cos((step / steps) * math.tau) * radius),
                int(cy + math.sin((step / steps) * math.tau) * radius),
            )
            for step in range(steps + 1)
        ]
    else:
        points = [(int(x), int(y)) for x, y in hit_zone["points"]]
        points.append(points[0])
    for start, end in zip(points, points[1:]):
        draw_line(pixels, width, height, start[0], start[1], end[0], end[1], color, 2, alpha)


def fill_polygon(
    pixels: bytearray,
    width: int,
    height: int,
    points: list[tuple[int, int]],
    color: tuple[int, int, int],
    alpha: float,
) -> None:
    min_y = max(0, min(y for _, y in points))
    max_y = min(height - 1, max(y for _, y in points))
    for y in range(min_y, max_y + 1):
        intersections: list[float] = []
        for index, (x1, y1) in enumerate(points):
            x2, y2 = points[(index + 1) % len(points)]
            if y1 == y2:
                continue
            if min(y1, y2) <= y < max(y1, y2):
                ratio = (y - y1) / (y2 - y1)
                intersections.append(x1 + ratio * (x2 - x1))
        intersections.sort()
        for index in range(0, len(intersections), 2):
            if index + 1 >= len(intersections):
                break
            x_start = max(0, int(math.ceil(intersections[index])))
            x_end = min(width - 1, int(math.floor(intersections[index + 1])))
            blend_span(pixels, width, y, x_start, x_end, color, alpha)


def draw_rect(
    pixels: bytearray,
    width: int,
    height: int,
    x: int,
    y: int,
    rect_width: int,
    rect_height: int,
    color: tuple[int, int, int],
    alpha: float,
) -> None:
    left = max(0, x)
    right = min(width - 1, x + rect_width)
    top = max(0, y)
    bottom = min(height - 1, y + rect_height)
    for row_y in range(top, bottom + 1):
        blend_span(pixels, width, row_y, left, right, color, alpha)


def draw_line(
    pixels: bytearray,
    width: int,
    height: int,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    color: tuple[int, int, int],
    radius: int,
    alpha: float,
) -> None:
    distance = max(1, math.hypot(x2 - x1, y2 - y1))
    steps = max(1, int(distance / max(1, radius / 2)))
    for step in range(steps + 1):
        t = step / steps
        x = int(x1 + (x2 - x1) * t)
        y = int(y1 + (y2 - y1) * t)
        draw_disc(pixels, width, height, x, y, radius, color, alpha)


def draw_disc(
    pixels: bytearray,
    width: int,
    height: int,
    cx: int,
    cy: int,
    radius: int,
    color: tuple[int, int, int],
    alpha: float,
) -> None:
    radius_sq = radius * radius
    left = max(0, cx - radius)
    right = min(width - 1, cx + radius)
    top = max(0, cy - radius)
    bottom = min(height - 1, cy + radius)
    for y in range(top, bottom + 1):
        dy = y - cy
        for x in range(left, right + 1):
            dx = x - cx
            if dx * dx + dy * dy <= radius_sq:
                blend_pixel(pixels, width, x, y, color, alpha)


def blend_span(
    pixels: bytearray,
    width: int,
    y: int,
    x_start: int,
    x_end: int,
    color: tuple[int, int, int],
    alpha: float,
) -> None:
    if x_end < x_start:
        return
    inv = 1 - alpha
    index = (y * width + x_start) * 3
    for _ in range(x_start, x_end + 1):
        pixels[index] = clamp(pixels[index] * inv + color[0] * alpha)
        pixels[index + 1] = clamp(pixels[index + 1] * inv + color[1] * alpha)
        pixels[index + 2] = clamp(pixels[index + 2] * inv + color[2] * alpha)
        index += 3


def blend_pixel(
    pixels: bytearray,
    width: int,
    x: int,
    y: int,
    color: tuple[int, int, int],
    alpha: float,
) -> None:
    if not (0 <= x < width and 0 <= y < len(pixels) // (width * 3)):
        return
    inv = 1 - alpha
    index = (y * width + x) * 3
    pixels[index] = clamp(pixels[index] * inv + color[0] * alpha)
    pixels[index + 1] = clamp(pixels[index + 1] * inv + color[1] * alpha)
    pixels[index + 2] = clamp(pixels[index + 2] * inv + color[2] * alpha)


def write_png(path: Path, width: int, height: int, pixels: bytearray) -> None:
    raw_rows = []
    row_width = width * 3
    for y in range(height):
        start = y * row_width
        raw_rows.append(b"\x00" + bytes(pixels[start : start + row_width]))
    compressed = zlib.compress(b"".join(raw_rows), level=9)
    with path.open("wb") as handle:
        handle.write(b"\x89PNG\r\n\x1a\n")
        handle.write(png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)))
        handle.write(png_chunk(b"IDAT", compressed))
        handle.write(png_chunk(b"IEND", b""))


def png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + chunk_type
        + data
        + struct.pack(">I", zlib.crc32(chunk_type + data) & 0xFFFFFFFF)
    )


def hash_noise(x: int, y: int) -> int:
    value = (x * 73856093) ^ (y * 19349663) ^ 0x4C4F5244
    value ^= value >> 13
    value *= 1274126177
    return (value ^ (value >> 16)) & 0xFF


def clamp(value: float) -> int:
    return max(0, min(255, int(value)))


if __name__ == "__main__":
    main()
