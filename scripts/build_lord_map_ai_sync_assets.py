from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = ROOT / "backend" / "witcher_larp" / "web" / "lord" / "assets"
REPORT_DIR = ROOT / "reports" / "map-debug-crops"
LAYOUT_PATH = ASSET_DIR / "lord_map_layout.json"
MAP_NODES_PATH = ROOT / "data" / "seed" / "map_nodes.csv"
MAP_EDGES_PATH = ROOT / "data" / "seed" / "map_edges.csv"

DEFAULT_PREFIX = "lord_map_ai_sync_v1"
DISPLAY_WIDTH = 3172

TERRAIN_PROMPTS = {
    "residence": "four noble residence rooms inside the central manor, visible as lordly house wings but not capturable castles",
    "fort": "small wooden and stone frontier fort with palisades, banners and compact yard",
    "field": "grain field, oat rows, hay tracks and open farm land",
    "village_barn": "barn village, sheds, hay roofs, muddy yard and carts",
    "resource_city": "well market, water source, small trading stalls and stone well",
    "magic_city": "subtle magical district, blue violet glow, ritual stones, no readable symbols",
    "science_city": "workshop and manufactory sheds, gears, timber, smoke, no modern factory",
    "forest": "dark Slavic forest or garden grove, winding roots and dense trees",
    "lake": "misty pond or moonlit water with reeds",
    "swamp": "black marsh, reeds, shallow water and muddy crossings",
    "mountain": "rocky ridge or watch cliff with gray stone paths",
    "no_play_zone": "background-only excluded building, muted and not highlighted",
}

TERRAIN_COLORS = {
    "residence": (178, 130, 76),
    "fort": (155, 132, 86),
    "field": (176, 153, 78),
    "village_barn": (147, 101, 60),
    "resource_city": (160, 122, 73),
    "magic_city": (109, 81, 151),
    "science_city": (125, 132, 110),
    "forest": (57, 108, 67),
    "lake": (58, 121, 143),
    "swamp": (55, 91, 78),
    "mountain": (136, 137, 125),
    "no_play_zone": (85, 75, 63),
}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build comparison assets for a new AI-generated lord map background.",
    )
    parser.add_argument("--prefix", default=DEFAULT_PREFIX)
    parser.add_argument(
        "--input",
        type=Path,
        default=None,
        help="Raw OpenRouter image. Defaults to backend lord assets/<prefix>_openrouter_raw.png.",
    )
    parser.add_argument(
        "--prepare-only",
        action="store_true",
        help="Only write generation prompt and technical guide, without compositing final assets.",
    )
    args = parser.parse_args()

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    layout = json.loads(LAYOUT_PATH.read_text(encoding="utf-8"))
    seed_nodes = load_seed_nodes()
    seed_edges = load_seed_edges()
    prefix = args.prefix

    prompt_path = REPORT_DIR / f"{prefix}-openrouter-prompt.md"
    guide_path = REPORT_DIR / f"{prefix}-generation-guide.png"
    write_prompt(prompt_path, layout, seed_nodes, seed_edges)
    write_generation_guide(guide_path, layout, seed_nodes)

    if args.prepare_only:
        print(f"prompt: {prompt_path}")
        print(f"guide: {guide_path}")
        return

    input_path = args.input or ASSET_DIR / f"{prefix}_openrouter_raw.png"
    if not input_path.exists():
        raise FileNotFoundError(
            f"Raw OpenRouter image not found: {input_path}. "
            f"Run the OpenRouter script first or pass --input."
        )

    width = int(layout["canvas"]["width"])
    height = int(layout["canvas"]["height"])
    base = fit_cover(Image.open(input_path).convert("RGB"), (width, height)).convert("RGBA")
    base = enhance_base(base)

    clean = base.copy()
    draw_canonical_roads(clean, layout)
    draw_subtle_landmark_glow(clean, layout, seed_nodes)

    dotted = clean.copy()
    draw_route_dots(dotted, layout)

    holes = cut_socket_holes(clean.copy(), layout)
    technical = clean.copy()
    draw_technical_graph(technical, layout, seed_nodes)
    technical_holes = cut_socket_holes(technical, layout)

    outputs = {
        "clean_png": ASSET_DIR / f"{prefix}_clean.png",
        "clean_webp": ASSET_DIR / f"{prefix}_clean.webp",
        "dotted_png": ASSET_DIR / f"{prefix}_dotted.png",
        "dotted_webp": ASSET_DIR / f"{prefix}_dotted.webp",
        "clean_holes_png": ASSET_DIR / f"{prefix}_clean_holes.png",
        "clean_holes_preview_png": ASSET_DIR / f"{prefix}_clean_holes_preview.png",
        "technical_graph_holes_png": REPORT_DIR / f"{prefix}-technical-graph-holes.png",
        "technical_graph_holes_preview_png": REPORT_DIR
        / f"{prefix}-technical-graph-holes-preview.png",
        "holes_json": ASSET_DIR / f"{prefix}_holes.json",
        "manifest_json": ASSET_DIR / f"{prefix}_manifest.json",
    }

    save_png_and_webp(clean, outputs["clean_png"], outputs["clean_webp"])
    save_png_and_webp(dotted, outputs["dotted_png"], outputs["dotted_webp"])
    save_png(holes, outputs["clean_holes_png"])
    write_hole_preview(holes, layout, outputs["clean_holes_preview_png"])
    save_png(technical_holes, outputs["technical_graph_holes_png"])
    write_hole_preview(technical_holes, layout, outputs["technical_graph_holes_preview_png"])

    hole_records = collect_holes(layout)
    outputs["holes_json"].write_text(
        json.dumps(
            {
                "layout_version": layout["version"],
                "layout_mode": layout["mode"],
                "source_image": str(input_path.relative_to(ROOT)).replace("\\", "/"),
                "clean_asset": outputs["clean_png"].name,
                "dotted_asset": outputs["dotted_png"].name,
                "holes_asset": outputs["clean_holes_png"].name,
                "holes": hole_records,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    outputs["manifest_json"].write_text(
        json.dumps(
            {
                "prefix": prefix,
                "layout_version": layout["version"],
                "layout_mode": layout["mode"],
                "old_runtime_asset_untouched": "lord_map_playable_v1_display.webp",
                "source_raw": str(input_path.relative_to(ROOT)).replace("\\", "/"),
                "prompt": str(prompt_path.relative_to(ROOT)).replace("\\", "/"),
                "guide": str(guide_path.relative_to(ROOT)).replace("\\", "/"),
                "outputs": {
                    key: str(path.relative_to(ROOT)).replace("\\", "/")
                    for key, path in outputs.items()
                    if key != "manifest_json"
                },
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    for label, path in outputs.items():
        print(f"{label}: {path}")


def load_seed_nodes() -> dict[str, dict[str, str]]:
    with MAP_NODES_PATH.open(encoding="utf-8", newline="") as handle:
        return {row["node_id"]: row for row in csv.DictReader(handle)}


def load_seed_edges() -> list[dict[str, str]]:
    with MAP_EDGES_PATH.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_prompt(
    target: Path,
    layout: dict[str, object],
    seed_nodes: dict[str, dict[str, str]],
    seed_edges: list[dict[str, str]],
) -> None:
    width = int(layout["canvas"]["width"])
    height = int(layout["canvas"]["height"])
    node_lines = []
    for node_id, node in layout["nodes"].items():
        seed = seed_nodes[node_id]
        if seed["zone_status"] == "no_play_excluded":
            continue
        x = int(node["x"]) / width
        y = int(node["y"]) / height
        node_lines.append(
            f"- {seed['name']} ({seed['node_type']}), normalized position {x:.3f}, {y:.3f}: "
            f"{TERRAIN_PROMPTS.get(seed['node_type'], 'dark fantasy territory')}."
        )

    edge_lines = []
    for edge in seed_edges:
        from_name = seed_nodes[edge["from_node_id"]]["name"]
        to_name = seed_nodes[edge["to_node_id"]]["name"]
        edge_lines.append(f"- {from_name} <-> {to_name}, MP {edge['mp_cost']}")

    target.write_text(
        "\n".join(
            [
                "# OpenRouter prompt: lord map AI sync v1",
                "",
                "Create one original high-end hand-painted dark fantasy strategy map background for a Witcher-like one-day LARP lord panel.",
                "Canvas should feel like a premium PC strategy game map, top-down/isometric painted board, not a satellite map and not a UI screen.",
                "Use a wide map composition close to 1.6:1. The final pipeline will crop/upscale to 9516x5952, so keep important details inside generous margins.",
                "",
                "Hard visual requirements:",
                "- Draw clear thematic territories and obvious dirt/stone roads between them, but do not draw any text, labels, numbers, UI panels, debug marks, dotted overlays, colored ownership circles, or watermarks.",
                "- Keep four lord residences visually inside the central manor/castle block. They are rooms/wings of one central house, not separate external castles.",
                "- Do not run any road straight through the central manor/castle body. Roads may leave residence gates, but the central house must remain visually readable and not be bisected.",
                "- The well market must connect through the eastern fort gateway, not through the oat field.",
                "- Roads must be sparse and planar: no road crossings, no dense web, approximately medieval footpaths between named places.",
                "- Leave small calm clearings around each territory center so a later technical circular marker can be placed there.",
                "- Style: grim Slavic medieval fantasy, parchment-earth palette with forest greens, swamp blacks, grey rock, muted lake blues, warm torch accents, painterly realism.",
                "- Avoid copied official Witcher, Warcraft, Heroes, Gwent or other copyrighted game art.",
                "",
                "Territory placement guide:",
                *node_lines,
                "",
                "Canonical road graph to respect:",
                *edge_lines,
                "",
                "Negative prompt: no readable text, no labels, no letters, no route numbers, no extra node circles, no modern buildings, no sci-fi, no flat vector map, no neon UI, no duplicated castles, no crossed roads, no road through the central manor.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def write_generation_guide(
    target: Path,
    layout: dict[str, object],
    seed_nodes: dict[str, dict[str, str]],
) -> None:
    scale = DISPLAY_WIDTH / int(layout["canvas"]["width"])
    width = DISPLAY_WIDTH
    height = round(int(layout["canvas"]["height"]) * scale)
    image = Image.new("RGB", (width, height), (42, 39, 31))
    draw = ImageDraw.Draw(image)

    for y in range(height):
        amount = y / max(1, height - 1)
        color = (
            round(55 + 18 * (1 - amount)),
            round(60 + 12 * (1 - amount)),
            round(45 + 10 * (1 - amount)),
        )
        draw.line([(0, y), (width, y)], fill=color)

    central = layout.get("central_house") or {}
    if central:
        box = [
            round(int(central["x"]) * scale),
            round(int(central["y"]) * scale),
            round((int(central["x"]) + int(central["w"])) * scale),
            round((int(central["y"]) + int(central["h"])) * scale),
        ]
        draw.rectangle(box, outline=(240, 120, 80), width=4, fill=(83, 61, 45))

    for edge in layout["edges"].values():
        points = [(round(x * scale), round(y * scale)) for x, y in edge["points"]]
        draw.line(points, fill=(235, 214, 145), width=7, joint="curve")
        draw.line(points, fill=(61, 41, 24), width=2, joint="curve")

    font = ImageFont.load_default()
    for node_id, node in layout["nodes"].items():
        seed = seed_nodes[node_id]
        x = round(int(node["x"]) * scale)
        y = round(int(node["y"]) * scale)
        radius = 15 if seed["zone_status"] != "no_play_excluded" else 10
        color = TERRAIN_COLORS.get(seed["node_type"], (190, 160, 92))
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=color, outline=(255, 238, 180), width=2)
        if seed["zone_status"] != "no_play_excluded":
            draw.text((x + radius + 5, y - radius), seed["name"], fill=(245, 235, 205), font=font)

    target.parent.mkdir(parents=True, exist_ok=True)
    image.save(target, optimize=True)


def fit_cover(image: Image.Image, target_size: tuple[int, int]) -> Image.Image:
    target_width, target_height = target_size
    scale = max(target_width / image.width, target_height / image.height)
    resized = image.resize(
        (math.ceil(image.width * scale), math.ceil(image.height * scale)),
        Image.Resampling.LANCZOS,
    )
    left = max(0, (resized.width - target_width) // 2)
    top = max(0, (resized.height - target_height) // 2)
    return resized.crop((left, top, left + target_width, top + target_height))


def enhance_base(image: Image.Image) -> Image.Image:
    vignette = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(vignette)
    width, height = image.size
    border = round(min(width, height) * 0.14)
    for step in range(border, 0, -16):
        alpha = round(78 * (1 - step / border) ** 1.9)
        draw.rectangle(
            (step, step, width - step, height - step),
            outline=(9, 8, 6, alpha),
            width=24,
        )
    image.alpha_composite(vignette.filter(ImageFilter.GaussianBlur(36)))
    return image


def draw_canonical_roads(image: Image.Image, layout: dict[str, object]) -> None:
    shadow = Image.new("RGBA", image.size, (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    player_paths = collect_player_road_paths(layout)
    for points in player_paths:
        shadow_draw.line(points, fill=(26, 18, 11, 76), width=64, joint="curve")
    image.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(12)))

    road = Image.new("RGBA", image.size, (0, 0, 0, 0))
    road_draw = ImageDraw.Draw(road)
    for index, points in enumerate(player_paths):
        road_draw.line(points, fill=(76, 53, 31, 108), width=46, joint="curve")
        road_draw.line(points, fill=(168, 133, 78, 148), width=31, joint="curve")
        road_draw.line(points, fill=(226, 196, 130, 44), width=10, joint="curve")
        draw_road_grit(road_draw, points, index)
    image.alpha_composite(road.filter(ImageFilter.GaussianBlur(0.65)))


def collect_player_road_paths(layout: dict[str, object]) -> list[list[tuple[int, int]]]:
    central = layout.get("central_house") or {}
    central_rect = None
    if central:
        padding = 38
        central_rect = (
            int(central["x"]) - padding,
            int(central["y"]) - padding,
            int(central["x"]) + int(central["w"]) + padding,
            int(central["y"]) + int(central["h"]) + padding,
        )

    paths: list[list[tuple[int, int]]] = []
    for edge in layout["edges"].values():
        points = [tuple(point) for point in edge["points"]]
        smoothed = chaikin(points, iterations=2)
        sampled = sample_polyline(smoothed, step=28)
        if central_rect is None:
            if len(sampled) >= 2:
                paths.append(sampled)
            continue
        paths.extend(split_outside_rect(sampled, central_rect))
    return [path for path in paths if len(path) >= 2]


def chaikin(points: list[tuple[int, int]], iterations: int) -> list[tuple[int, int]]:
    result = [(float(x), float(y)) for x, y in points]
    for _ in range(iterations):
        if len(result) < 3:
            break
        smoothed = [result[0]]
        for start, end in zip(result, result[1:]):
            x1, y1 = start
            x2, y2 = end
            smoothed.append((x1 * 0.75 + x2 * 0.25, y1 * 0.75 + y2 * 0.25))
            smoothed.append((x1 * 0.25 + x2 * 0.75, y1 * 0.25 + y2 * 0.75))
        smoothed.append(result[-1])
        result = smoothed
    return [(round(x), round(y)) for x, y in result]


def sample_polyline(points: list[tuple[int, int]], step: int) -> list[tuple[int, int]]:
    sampled: list[tuple[int, int]] = []
    for start, end in zip(points, points[1:]):
        x1, y1 = start
        x2, y2 = end
        distance = max(1.0, math.hypot(x2 - x1, y2 - y1))
        count = max(1, math.ceil(distance / step))
        for index in range(count):
            t = index / count
            sampled.append((round(x1 + (x2 - x1) * t), round(y1 + (y2 - y1) * t)))
    sampled.append(points[-1])
    return sampled


def split_outside_rect(
    points: list[tuple[int, int]],
    rect: tuple[int, int, int, int],
) -> list[list[tuple[int, int]]]:
    chunks: list[list[tuple[int, int]]] = []
    current: list[tuple[int, int]] = []
    for point in points:
        if point_in_rect(point, rect):
            if len(current) >= 2:
                chunks.append(current)
            current = []
            continue
        current.append(point)
    if len(current) >= 2:
        chunks.append(current)
    return chunks


def point_in_rect(point: tuple[int, int], rect: tuple[int, int, int, int]) -> bool:
    x, y = point
    left, top, right, bottom = rect
    return left <= x <= right and top <= y <= bottom


def draw_road_grit(
    draw: ImageDraw.ImageDraw,
    points: list[tuple[int, int]],
    salt: int,
) -> None:
    for segment_index, (start, end) in enumerate(zip(points, points[1:])):
        x1, y1 = start
        x2, y2 = end
        dx = x2 - x1
        dy = y2 - y1
        distance = max(1.0, math.hypot(dx, dy))
        normal_x = -dy / distance
        normal_y = dx / distance
        steps = max(2, int(distance // 180))
        for step in range(1, steps):
            seed = salt * 101 + segment_index * 37 + step * 19
            t = step / steps
            side = -1 if seed % 2 else 1
            spread = 18 + seed % 23
            cx = x1 + dx * t + normal_x * spread * side
            cy = y1 + dy * t + normal_y * spread * side
            radius = 4 + seed % 9
            fill = (240, 210, 145, 42) if seed % 3 else (38, 27, 17, 48)
            draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=fill)


def draw_subtle_landmark_glow(
    image: Image.Image,
    layout: dict[str, object],
    seed_nodes: dict[str, dict[str, str]],
) -> None:
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    for node_id, node in layout["nodes"].items():
        seed = seed_nodes[node_id]
        if seed["zone_status"] == "no_play_excluded":
            continue
        color = TERRAIN_COLORS.get(seed["node_type"], (190, 160, 92))
        cx = int(node["x"])
        cy = int(node["y"])
        radius = int((node.get("ownership_socket") or node["hit_zone"])["r"]) + 24
        draw.ellipse(
            (cx - radius, cy - radius, cx + radius, cy + radius),
            fill=(*color, 22),
        )
    image.alpha_composite(layer.filter(ImageFilter.GaussianBlur(16)))


def draw_route_dots(image: Image.Image, layout: dict[str, object]) -> None:
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    for points in collect_player_road_paths(layout):
        for start, end in zip(points, points[1:]):
            draw_dashed_segment(draw, start, end)
    image.alpha_composite(layer)


def draw_dashed_segment(
    draw: ImageDraw.ImageDraw,
    start: tuple[int, int],
    end: tuple[int, int],
) -> None:
    x1, y1 = start
    x2, y2 = end
    dx = x2 - x1
    dy = y2 - y1
    distance = max(1.0, math.hypot(dx, dy))
    dash = 30
    gap = 34
    cursor = 18
    while cursor < distance:
        t1 = cursor / distance
        t2 = min(distance, cursor + dash) / distance
        segment = (
            (x1 + dx * t1, y1 + dy * t1),
            (x1 + dx * t2, y1 + dy * t2),
        )
        draw.line(segment, fill=(38, 23, 10, 215), width=14)
        draw.line(segment, fill=(248, 220, 146, 188), width=6)
        cursor += dash + gap


def cut_socket_holes(image: Image.Image, layout: dict[str, object]) -> Image.Image:
    alpha = image.getchannel("A")
    for hole in collect_holes(layout):
        cx = int(hole["cx"])
        cy = int(hole["cy"])
        radius = int(hole["radius"])
        mask = Image.new("L", image.size, 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=255)
        mask = mask.filter(ImageFilter.GaussianBlur(6))
        alpha.paste(0, mask=mask)
    image.putalpha(alpha)
    return image


def collect_holes(layout: dict[str, object]) -> list[dict[str, object]]:
    holes = []
    for node_id, node in layout["nodes"].items():
        socket = node.get("ownership_socket")
        if not socket:
            continue
        holes.append(
            {
                "node_id": node_id,
                "cx": round(float(socket["cx"])),
                "cy": round(float(socket["cy"])),
                "radius": round(float(socket["r"]) * 0.92),
            }
        )
    return holes


def draw_technical_graph(
    image: Image.Image,
    layout: dict[str, object],
    seed_nodes: dict[str, dict[str, str]],
) -> None:
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    central = layout.get("central_house") or {}
    if central:
        box = (
            int(central["x"]),
            int(central["y"]),
            int(central["x"]) + int(central["w"]),
            int(central["y"]) + int(central["h"]),
        )
        draw.rectangle(box, outline=(255, 92, 74, 180), width=16)

    for edge in layout["edges"].values():
        points = [tuple(point) for point in edge["points"]]
        draw.line(points, fill=(49, 230, 117, 210), width=18, joint="curve")
        draw.line(points, fill=(8, 42, 22, 210), width=5, joint="curve")

    font = ImageFont.load_default()
    for node_id, node in layout["nodes"].items():
        seed = seed_nodes[node_id]
        x = int(node["x"])
        y = int(node["y"])
        radius = 118 if seed["zone_status"] != "no_play_excluded" else 80
        outline = (255, 239, 169, 235) if seed["zone_status"] != "no_play_excluded" else (168, 168, 168, 190)
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), outline=outline, width=12)
        if seed["zone_status"] != "no_play_excluded":
            draw.text((x + radius + 18, y - 28), seed["name"], fill=(255, 249, 205, 245), font=font)

    image.alpha_composite(overlay)


def write_hole_preview(
    image: Image.Image,
    layout: dict[str, object],
    target: Path,
) -> None:
    underlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(underlay)
    colors = [(174, 47, 52, 255), (61, 123, 195, 255), (62, 151, 91, 255), (190, 143, 47, 255)]
    for index, hole in enumerate(collect_holes(layout)):
        cx = int(hole["cx"])
        cy = int(hole["cy"])
        radius = int(hole["radius"]) + 12
        draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=colors[index % len(colors)])
    save_png(Image.alpha_composite(underlay, image), target)


def save_png_and_webp(image: Image.Image, png_path: Path, webp_path: Path) -> None:
    save_png(image.convert("RGB"), png_path)
    display_height = round(image.height * (DISPLAY_WIDTH / image.width))
    display = image.convert("RGB").resize((DISPLAY_WIDTH, display_height), Image.Resampling.LANCZOS)
    save_webp(display, webp_path)


def save_png(image: Image.Image, target: Path) -> None:
    temp = target.with_name(f"{target.name}.tmp")
    temp.unlink(missing_ok=True)
    image.save(temp, "PNG", compress_level=6)
    temp.replace(target)


def save_webp(image: Image.Image, target: Path) -> None:
    temp = target.with_name(f"{target.name}.tmp")
    temp.unlink(missing_ok=True)
    image.save(temp, "WEBP", quality=90, method=6)
    temp.replace(target)


if __name__ == "__main__":
    main()
