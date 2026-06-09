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

DEFAULT_PREFIX = "lord_map_ai_strict_v6"
DISPLAY_WIDTH = 3172
RESIDENCE_NODE_IDS = {
    "node_res_north",
    "node_res_river",
    "node_res_forest",
    "node_res_hill",
}

OWNER_COLORS = {
    "node_res_north": (63, 127, 184, 238),
    "node_res_river": (201, 75, 67, 238),
    "node_res_forest": (63, 155, 96, 238),
    "node_res_hill": (211, 168, 70, 238),
}
NEUTRAL = (141, 138, 130, 235)

TERRAIN_COLORS = {
    "residence": (184, 124, 78),
    "fort": (142, 126, 92),
    "field": (178, 153, 80),
    "village_barn": (154, 102, 58),
    "resource_city": (180, 145, 88),
    "magic_city": (112, 84, 156),
    "science_city": (119, 128, 111),
    "forest": (62, 115, 72),
    "lake": (60, 124, 150),
    "swamp": (51, 88, 78),
    "mountain": (145, 143, 130),
    "no_play_zone": (86, 76, 64),
}

TERRAIN_PROMPTS = {
    "residence": "a lord residence room or courtyard inside the single central castle, not a separate castle",
    "fort": "a small frontier fort, palisade, compact guard yard",
    "field": "grain fields and farm clearings without road tracks",
    "village_barn": "a small barn village, sheds, hay roofs, muddy yard",
    "resource_city": "a stone well market with small trading stalls",
    "magic_city": "subtle magic landmark, ritual stones, blue-violet glow",
    "science_city": "a medieval manufactory/workshop with timber sheds and smoke",
    "forest": "a dark forest or garden grove with dense trees",
    "lake": "a misty lake or pond with reeds",
    "swamp": "black marsh, reeds, shallow water and dead trees",
    "mountain": "rocky ridge, grey cliff, alpine watch point",
}

# Visual-space placement for the strict generated 3:2 artwork. The graph node
# ids stay canonical; only the painted map centers are art-specific.
STRICT_V6_DISPLAY_POINTS = {
    "node_res_north": (1260, 740),
    "node_res_river": (1720, 740),
    "node_res_forest": (1260, 970),
    "node_res_hill": (1720, 970),
    "node_fort_east": (1590, 300),
    "node_fort_west": (875, 330),
    "node_fort_southwest": (650, 1460),
    "node_field_oats": (1015, 500),
    "node_field_west_large": (470, 580),
    "node_field_east_large": (2630, 1260),
    "node_village_barn": (1550, 1290),
    "node_village_east_shed": (2395, 850),
    "node_well_city": (2255, 555),
    "node_spanish_magic": (1410, 1715),
    "node_science_barn": (1975, 1535),
    "node_forest_dark": (625, 985),
    "node_forest_south_garden": (2285, 1555),
    "node_lake_mist": (2560, 805),
    "node_lake_south_pond": (2700, 1675),
    "node_swamp_black": (580, 1190),
    "node_mountain_north_alpine": (2145, 365),
    "node_mountain_gray": (2055, 1215),
    "node_mountain_west_alpine": (1040, 1625),
}

STRICT_V6_EDGE_DISPLAY_PATHS = {
    "edge_north_field": [(1260, 740), (1205, 650), (1125, 570), (1015, 500)],
    "edge_north_fort_east": [(1260, 740), (1320, 600), (1450, 450), (1590, 300)],
    "edge_fort_east_mountain_north": [(1590, 300), (1790, 315), (1990, 320), (2145, 365)],
    "edge_fort_west_field_north": [(875, 330), (925, 405), (1015, 500)],
    "edge_fort_west_field_west": [(875, 330), (720, 395), (560, 500), (470, 580)],
    "edge_fort_west_fort_east": [(875, 330), (1080, 285), (1330, 265), (1590, 300)],
    "edge_field_west_forest_dark": [(470, 580), (515, 760), (625, 985)],
    "edge_swamp_forest_west": [(580, 1190), (595, 1085), (625, 985)],
    "edge_swamp_fort_southwest": [(580, 1190), (605, 1325), (650, 1460)],
    "edge_forest_fort_southwest": [(1260, 970), (1075, 1115), (880, 1265), (705, 1385), (650, 1460)],
    "edge_fort_southwest_mountain_west": [(650, 1460), (800, 1560), (1040, 1625)],
    "edge_forest_village": [(1260, 970), (1385, 1125), (1550, 1290)],
    "edge_village_magic": [(1550, 1290), (1500, 1490), (1410, 1715)],
    "edge_village_mountain_gray": [(1550, 1290), (1735, 1265), (1905, 1235), (2055, 1215)],
    "edge_magic_science": [(1410, 1715), (1620, 1645), (1975, 1535)],
    "edge_science_forest_south": [(1975, 1535), (2110, 1545), (2285, 1555)],
    "edge_forest_south_lake_south": [(2285, 1555), (2510, 1590), (2700, 1675)],
    "edge_field_east_science": [(2630, 1260), (2440, 1370), (2210, 1480), (1975, 1535)],
    "edge_hill_field_east": [(1720, 970), (1960, 1030), (2300, 1120), (2630, 1260)],
    "edge_hill_mountain": [(1720, 970), (1845, 1090), (2055, 1215)],
    "edge_village_east_well": [(2395, 850), (2330, 715), (2255, 555)],
    "edge_village_east_lake": [(2395, 850), (2485, 835), (2560, 805)],
    "edge_lake_field_east": [(2560, 805), (2570, 1010), (2630, 1260)],
    "edge_river_well": [(1720, 740), (1900, 690), (2105, 620), (2255, 555)],
    "edge_river_village_east": [(1720, 740), (1910, 770), (2160, 815), (2395, 850)],
    "edge_fort_east_well": [(1590, 300), (1800, 350), (2055, 450), (2255, 555)],
}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a strict lord map where baked roads come only from map_edges.csv.",
    )
    parser.add_argument("--prefix", default=DEFAULT_PREFIX)
    parser.add_argument(
        "--input",
        type=Path,
        default=None,
        help="Raw roadless OpenRouter image. Defaults to backend lord assets/<prefix>_openrouter_raw.png.",
    )
    parser.add_argument(
        "--prepare-only",
        action="store_true",
        help="Write prompt/guide assets only.",
    )
    args = parser.parse_args()

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    prefix = args.prefix
    layout = json.loads(LAYOUT_PATH.read_text(encoding="utf-8"))
    seed_nodes = load_seed_nodes()
    seed_edges = load_seed_edges()

    prompt_path = REPORT_DIR / f"{prefix}-openrouter-prompt.md"
    skeleton_path = REPORT_DIR / f"{prefix}-skeleton-guide.png"
    annotated_path = REPORT_DIR / f"{prefix}-annotated-guide.png"
    write_prompt(prompt_path, layout, seed_nodes, seed_edges)
    write_skeleton_guide(skeleton_path, layout, seed_nodes, labels=False)
    write_skeleton_guide(annotated_path, layout, seed_nodes, labels=True)

    if args.prepare_only:
        print(f"prompt: {prompt_path}")
        print(f"skeleton: {skeleton_path}")
        print(f"annotated: {annotated_path}")
        return

    input_path = args.input or ASSET_DIR / f"{prefix}_openrouter_raw.png"
    if not input_path.exists():
        raise FileNotFoundError(
            f"Raw roadless image not found: {input_path}. Run OpenRouter generation first."
        )

    size = (int(layout["canvas"]["width"]), int(layout["canvas"]["height"]))
    base = fit_preserve(Image.open(input_path).convert("RGB"), size).convert("RGBA")
    base = finish_base(base)
    sockets = collect_sockets(size)
    roads = collect_road_paths(size, seed_edges, layout)

    baked = base.copy()
    draw_baked_roads(baked, roads)

    dotted = baked.copy()
    draw_route_dots(dotted, roads)

    holes = draw_socket_rims(baked.copy(), sockets, cut_holes=True)
    neutral_preview = draw_preview(baked.copy(), sockets, owner_mode=False)
    owner_preview = draw_preview(baked.copy(), sockets, owner_mode=True)
    road_debug = draw_road_debug(base.copy(), sockets, roads)
    audit = build_road_audit(seed_edges, roads, layout)

    output_paths = {
        "base_png": ASSET_DIR / f"{prefix}_roadless_base.png",
        "base_webp": ASSET_DIR / f"{prefix}_roadless_base.webp",
        "baked_roads_png": ASSET_DIR / f"{prefix}_baked_roads.png",
        "baked_roads_webp": ASSET_DIR / f"{prefix}_baked_roads.webp",
        "dotted_png": ASSET_DIR / f"{prefix}_baked_roads_dotted.png",
        "dotted_webp": ASSET_DIR / f"{prefix}_baked_roads_dotted.webp",
        "holes_png": ASSET_DIR / f"{prefix}_territory_sockets_holes.png",
        "neutral_preview_png": ASSET_DIR / f"{prefix}_territory_sockets_neutral_preview.png",
        "owner_preview_png": ASSET_DIR / f"{prefix}_territory_sockets_owner_preview.png",
        "owner_preview_webp": ASSET_DIR / f"{prefix}_territory_sockets_owner_preview.webp",
        "holes_json": ASSET_DIR / f"{prefix}_territory_sockets_holes.json",
        "manifest_json": ASSET_DIR / f"{prefix}_manifest.json",
        "road_debug_webp": REPORT_DIR / f"{prefix}-road-debug.webp",
        "road_audit_json": REPORT_DIR / f"{prefix}-road-audit.json",
    }

    save_png(base.convert("RGB"), output_paths["base_png"])
    save_display_webp(base.convert("RGB"), output_paths["base_webp"])
    save_png(baked.convert("RGB"), output_paths["baked_roads_png"])
    save_display_webp(baked.convert("RGB"), output_paths["baked_roads_webp"])
    save_png(dotted.convert("RGB"), output_paths["dotted_png"])
    save_display_webp(dotted.convert("RGB"), output_paths["dotted_webp"])
    save_png(holes, output_paths["holes_png"])
    save_png(neutral_preview, output_paths["neutral_preview_png"])
    save_png(owner_preview, output_paths["owner_preview_png"])
    save_display_webp(owner_preview.convert("RGB"), output_paths["owner_preview_webp"])
    save_display_webp(road_debug.convert("RGB"), output_paths["road_debug_webp"])

    output_paths["holes_json"].write_text(
        json.dumps(
            {
                "asset": output_paths["holes_png"].name,
                "source_asset": output_paths["baked_roads_png"].name,
                "layout_version": layout["version"],
                "layout_mode": layout["mode"],
                "placement": "strict_v6_west_fort_gray_watch_baked_roads",
                "holes": [
                    {
                        "node_id": socket["node_id"],
                        "cx": socket["cx"],
                        "cy": socket["cy"],
                        "radius": socket["hole_r"],
                    }
                    for socket in sockets
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    output_paths["road_audit_json"].write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    output_paths["manifest_json"].write_text(
        json.dumps(
            {
                "prefix": prefix,
                "layout_version": layout["version"],
                "layout_mode": layout["mode"],
                "source_raw": str(input_path.relative_to(ROOT)).replace("\\", "/"),
                "prompt": str(prompt_path.relative_to(ROOT)).replace("\\", "/"),
                "skeleton_guide": str(skeleton_path.relative_to(ROOT)).replace("\\", "/"),
                "annotated_guide": str(annotated_path.relative_to(ROOT)).replace("\\", "/"),
                "baked_road_contract": {
                    "road_source": str(MAP_EDGES_PATH.relative_to(ROOT)).replace("\\", "/"),
                    "road_paths_source": "STRICT_V6_EDGE_DISPLAY_PATHS",
                    "ai_road_policy": "AI road drawing is forbidden; all visible roads are postprocessed from the graph.",
                    "audit": str(output_paths["road_audit_json"].relative_to(ROOT)).replace("\\", "/"),
                },
                "outputs": {
                    key: str(path.relative_to(ROOT)).replace("\\", "/")
                    for key, path in output_paths.items()
                    if key != "manifest_json"
                },
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    for label, path in output_paths.items():
        print(f"{label}: {path}")


def load_seed_nodes() -> dict[str, dict[str, str]]:
    with MAP_NODES_PATH.open(encoding="utf-8", newline="") as handle:
        return {row["node_id"]: row for row in csv.DictReader(handle)}


def load_seed_edges() -> list[dict[str, str]]:
    with MAP_EDGES_PATH.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_prompt(
    target: Path,
    layout: dict,
    seed_nodes: dict[str, dict[str, str]],
    seed_edges: list[dict[str, str]],
) -> None:
    node_lines = []
    for node_id, seed in seed_nodes.items():
        if seed["zone_status"] == "no_play_excluded":
            continue
        point = STRICT_V6_DISPLAY_POINTS[node_id]
        node_lines.append(
            f"- {seed['name']}: {TERRAIN_PROMPTS.get(seed['node_type'], seed['node_type'])}, "
            f"position x={point[0] / DISPLAY_WIDTH:.3f}, y={point[1] / round(DISPLAY_WIDTH * 2 / 3):.3f}."
        )

    edge_lines = []
    for edge in seed_edges:
        from_name = seed_nodes[edge["from_node_id"]]["name"]
        to_name = seed_nodes[edge["to_node_id"]]["name"]
        edge_lines.append(f"- {from_name} to {to_name} (drawn later by code, MP {edge['mp_cost']})")

    target.write_text(
        "\n".join(
            [
                "# Strict v6 OpenRouter prompt: roadless lord map base",
                "",
                "Use the attached guide only as a private composition guide for landmark placement.",
                "Do not copy guide dots, labels, technical colors, rings, graph marks, or any UI elements.",
                "",
                "Generate one finished original high-end hand-painted dark fantasy strategy map background.",
                "The image must be roadless: do not draw roads, footpaths, trails, tracks, routes, dotted paths, bridges-as-routes, fork lines, path lines, or shortcut lines anywhere.",
                "Roads will be drawn later by deterministic code from the game graph, so every visible route-like stroke in your image would be wrong.",
                "",
                "Composition requirements:",
                "- Exactly one large central castle/manor. It contains four distinct lord starting rooms/courtyards/wings/gates inside one building.",
                f"- Around the castle, paint exactly {len(node_lines) - 4} non-start territories as clear themed landmarks.",
                "- Keep each landmark near its guide position and leave a calm circular clearing for a later game marker.",
                "- The terrain between landmarks must be natural ground, forest, water, rock, fields or swamp, but not road-shaped.",
                "- Do not connect landmarks visually with paths. Do not imply unlisted shortcuts.",
                "- No text, no readable letters, no numbers, no labels, no ownership colors, no circles, no UI frame, no watermarks.",
                "",
                "Landmarks and approximate positions:",
                *node_lines,
                "",
                "The future road graph is listed only so you understand which places must remain visually connectable later. Do not draw these roads now:",
                *edge_lines,
                "",
                "Art direction:",
                "- Grim Slavic medieval fantasy, Witcher-like mood without using official Witcher assets.",
                "- Top-down/isometric painted strategy map, readable landmarks, rich terrain, original local/generated art.",
                "- Fields, forts, forests, lakes, swamp, mountains, well market, magic stones, manufactory and villages should be thematically obvious.",
                "",
                "Negative prompt: road, roads, trail, trails, path, paths, track, tracks, route, routes, dotted line, dashed line, graph overlay, labels, map pins, colored circles, extra castles, modern roads, sci-fi, vector diagram, technical blueprint.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def write_skeleton_guide(
    target: Path,
    layout: dict,
    seed_nodes: dict[str, dict[str, str]],
    *,
    labels: bool,
) -> None:
    image = Image.new("RGB", (DISPLAY_WIDTH, round(DISPLAY_WIDTH * 2 / 3)), (39, 36, 30))
    draw = ImageDraw.Draw(image)

    central = layout.get("central_house") or {}
    if central:
        scale = DISPLAY_WIDTH / int(layout["canvas"]["width"])
        box = (
            round(int(central["x"]) * scale),
            round(int(central["y"]) * scale),
            round((int(central["x"]) + int(central["w"])) * scale),
            round((int(central["y"]) + int(central["h"])) * scale),
        )
        draw.rectangle(box, outline=(176, 112, 72), width=4, fill=(78, 57, 43))

    font = ImageFont.load_default()
    for node_id, seed in seed_nodes.items():
        if seed["zone_status"] == "no_play_excluded":
            continue
        x, y = STRICT_V6_DISPLAY_POINTS[node_id]
        radius = 17 if seed["node_type"] == "residence" else 13
        color = TERRAIN_COLORS.get(seed["node_type"], (204, 174, 104))
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=color, outline=(247, 226, 166), width=2)
        if labels:
            draw.text((x + radius + 6, y - radius), seed["name"], fill=(248, 236, 200), font=font)

    if labels:
        draw.text(
            (20, 20),
            "Roadless base guide: render landmarks, not dots/labels/roads.",
            fill=(248, 236, 200),
            font=font,
        )

    target.parent.mkdir(parents=True, exist_ok=True)
    image.save(target, "PNG", compress_level=6)


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


def fit_preserve(image: Image.Image, target_size: tuple[int, int]) -> Image.Image:
    target_width, target_height = target_size
    scale = min(target_width / image.width, target_height / image.height)
    foreground = image.resize(
        (math.floor(image.width * scale), math.floor(image.height * scale)),
        Image.Resampling.LANCZOS,
    )
    background = fit_cover(image, target_size).filter(ImageFilter.GaussianBlur(34))
    overlay = Image.new("RGB", target_size, (0, 0, 0))
    overlay.paste(background)
    left = (target_width - foreground.width) // 2
    top = (target_height - foreground.height) // 2
    overlay.paste(foreground, (left, top))
    return overlay


def finish_base(image: Image.Image) -> Image.Image:
    image = image.filter(ImageFilter.UnsharpMask(radius=1.4, percent=118, threshold=3))
    vignette = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(vignette)
    width, height = image.size
    border = round(min(width, height) * 0.11)
    for step in range(border, 0, -18):
        alpha = round(54 * (1 - step / border) ** 1.8)
        draw.rectangle((step, step, width - step, height - step), outline=(8, 7, 5, alpha), width=26)
    image.alpha_composite(vignette.filter(ImageFilter.GaussianBlur(34)))
    return image


def collect_sockets(size: tuple[int, int]) -> list[dict[str, int | str]]:
    radius = round(80 * (size[0] / 9516))
    sockets = []
    for node_id, point in STRICT_V6_DISPLAY_POINTS.items():
        cx, cy = scale_display_point(point, size)
        sockets.append(
            {
                "node_id": node_id,
                "cx": cx,
                "cy": cy,
                "outer_r": round(radius * 1.23),
                "rim_r": round(radius * 1.06),
                "hole_r": radius,
            }
        )
    return sockets


def collect_road_paths(
    size: tuple[int, int],
    edges: list[dict[str, str]],
    layout: dict,
) -> list[dict[str, object]]:
    central = layout.get("central_house") or {}
    clip_rect = None
    if central:
        padding = round(42 * (size[0] / 9516))
        clip_rect = (
            int(central["x"]) - padding,
            int(central["y"]) - padding,
            int(central["x"]) + int(central["w"]) + padding,
            int(central["y"]) + int(central["h"]) + padding,
        )

    roads = []
    for edge in edges:
        edge_id = edge["edge_id"]
        raw_path = STRICT_V6_EDGE_DISPLAY_PATHS[edge_id]
        scaled = [scale_display_point(point, size) for point in raw_path]
        smoothed = sample_polyline(chaikin(scaled, iterations=2), step=22)
        is_residence_edge = edge_touches_residence(edge)
        visible_segments = (
            [smoothed]
            if is_residence_edge or not clip_rect
            else split_outside_rect(smoothed, clip_rect)
        )
        roads.append(
            {
                "edge_id": edge_id,
                "from_node_id": edge["from_node_id"],
                "to_node_id": edge["to_node_id"],
                "is_residence_edge": is_residence_edge,
                "source_path": scaled,
                "paint_segments": [segment for segment in visible_segments if len(segment) >= 2],
            }
        )
    return roads


def edge_touches_residence(edge: dict[str, str]) -> bool:
    return (
        edge["from_node_id"] in RESIDENCE_NODE_IDS
        or edge["to_node_id"] in RESIDENCE_NODE_IDS
    )


def scale_display_point(point: tuple[int, int], size: tuple[int, int]) -> tuple[int, int]:
    scale = size[0] / DISPLAY_WIDTH
    return round(point[0] * scale), round(point[1] * scale)


def chaikin(points: list[tuple[int, int]], iterations: int) -> list[tuple[int, int]]:
    result = [(float(x), float(y)) for x, y in points]
    for _ in range(iterations):
        if len(result) < 3:
            break
        smoothed = [result[0]]
        for start, end in zip(result, result[1:]):
            x1, y1 = start
            x2, y2 = end
            smoothed.append((x1 * 0.76 + x2 * 0.24, y1 * 0.76 + y2 * 0.24))
            smoothed.append((x1 * 0.24 + x2 * 0.76, y1 * 0.24 + y2 * 0.76))
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
    rect: tuple[int, int, int, int] | None,
) -> list[list[tuple[int, int]]]:
    if rect is None:
        return [points]
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


def draw_baked_roads(image: Image.Image, roads: list[dict[str, object]]) -> None:
    shadow = Image.new("RGBA", image.size, (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    for road in roads:
        for segment in road["paint_segments"]:
            shadow_draw.line(segment, fill=(24, 16, 9, 84), width=58, joint="curve")
    image.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(10)))

    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    for index, road in enumerate(roads):
        for segment in road["paint_segments"]:
            draw.line(segment, fill=(69, 49, 29, 126), width=42, joint="curve")
            draw.line(segment, fill=(164, 129, 76, 162), width=29, joint="curve")
            draw.line(segment, fill=(229, 199, 133, 50), width=10, joint="curve")
            draw_road_grit(draw, segment, index)
    image.alpha_composite(layer.filter(ImageFilter.GaussianBlur(0.55)))


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
        steps = max(2, int(distance // 165))
        for step in range(1, steps):
            seed = salt * 101 + segment_index * 37 + step * 19
            t = step / steps
            side = -1 if seed % 2 else 1
            spread = 14 + seed % 21
            cx = x1 + dx * t + normal_x * spread * side
            cy = y1 + dy * t + normal_y * spread * side
            radius = 3 + seed % 8
            fill = (238, 205, 136, 42) if seed % 3 else (36, 25, 16, 50)
            draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=fill)


def draw_route_dots(image: Image.Image, roads: list[dict[str, object]]) -> None:
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    for road in roads:
        for segment in road["paint_segments"]:
            for start, end in zip(segment, segment[1:]):
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
    dash = 32
    gap = 36
    cursor = 18
    while cursor < distance:
        t1 = cursor / distance
        t2 = min(distance, cursor + dash) / distance
        dash_segment = (
            (x1 + dx * t1, y1 + dy * t1),
            (x1 + dx * t2, y1 + dy * t2),
        )
        draw.line(dash_segment, fill=(33, 20, 9, 220), width=14)
        draw.line(dash_segment, fill=(248, 220, 146, 188), width=6)
        cursor += dash + gap


def draw_socket_rims(
    image: Image.Image,
    sockets: list[dict[str, int | str]],
    *,
    cut_holes: bool,
) -> Image.Image:
    shadow = Image.new("RGBA", image.size, (0, 0, 0, 0))
    rim = Image.new("RGBA", image.size, (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    rim_draw = ImageDraw.Draw(rim)

    for socket in sockets:
        cx = int(socket["cx"])
        cy = int(socket["cy"])
        outer_r = int(socket["outer_r"])
        rim_r = int(socket["rim_r"])
        hole_r = int(socket["hole_r"])
        shadow_draw.ellipse(
            (cx - outer_r - 10, cy - outer_r - 7, cx + outer_r + 10, cy + outer_r + 13),
            fill=(8, 7, 5, 155),
        )
        rim_draw.ellipse(
            (cx - outer_r, cy - outer_r, cx + outer_r, cy + outer_r),
            fill=(28, 24, 18, 242),
        )
        rim_draw.ellipse(
            (cx - rim_r, cy - rim_r, cx + rim_r, cy + rim_r),
            fill=(226, 205, 158, 250),
        )
        rim_draw.ellipse(
            (cx - hole_r - 10, cy - hole_r - 10, cx + hole_r + 10, cy + hole_r + 10),
            fill=(34, 30, 23, 255),
        )
        rim_draw.ellipse(
            (cx - hole_r, cy - hole_r, cx + hole_r, cy + hole_r),
            fill=(190, 184, 168, 255),
        )

    image.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(7)))
    image.alpha_composite(rim)

    if cut_holes:
        alpha = image.getchannel("A")
        mask = Image.new("L", image.size, 0)
        draw = ImageDraw.Draw(mask)
        for socket in sockets:
            cx = int(socket["cx"])
            cy = int(socket["cy"])
            hole_r = int(socket["hole_r"])
            draw.ellipse((cx - hole_r, cy - hole_r, cx + hole_r, cy + hole_r), fill=255)
        mask = mask.filter(ImageFilter.GaussianBlur(3))
        alpha.paste(0, mask=mask)
        image.putalpha(alpha)

    return image


def draw_preview(
    image: Image.Image,
    sockets: list[dict[str, int | str]],
    *,
    owner_mode: bool,
) -> Image.Image:
    underlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(underlay)
    for socket in sockets:
        cx = int(socket["cx"])
        cy = int(socket["cy"])
        radius = int(socket["hole_r"]) + 2
        color = OWNER_COLORS.get(str(socket["node_id"]), NEUTRAL) if owner_mode else NEUTRAL
        draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=color)

    holes = draw_socket_rims(image, sockets, cut_holes=True)
    return Image.alpha_composite(underlay, holes)


def draw_road_debug(
    image: Image.Image,
    sockets: list[dict[str, int | str]],
    roads: list[dict[str, object]],
) -> Image.Image:
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    for road in roads:
        for segment in road["paint_segments"]:
            draw.line(segment, fill=(12, 10, 8, 220), width=20, joint="curve")
            draw.line(segment, fill=(88, 226, 130, 220), width=8, joint="curve")
    image.alpha_composite(layer)
    return draw_preview(image, sockets, owner_mode=True)


def build_road_audit(
    seed_edges: list[dict[str, str]],
    roads: list[dict[str, object]],
    layout: dict,
) -> dict[str, object]:
    expected_edge_ids = {edge["edge_id"] for edge in seed_edges}
    drawn_edge_ids = {str(road["edge_id"]) for road in roads}
    segments = collect_segments_for_audit(roads)
    intersections = find_intersections(segments)
    central_hits = count_central_hits(segments, layout, include_residence_edges=False)
    residence_central_hits = count_central_hits(segments, layout, include_residence_edges=True)
    endpoint_mismatches = []
    for edge in seed_edges:
        path = STRICT_V6_EDGE_DISPLAY_PATHS.get(edge["edge_id"])
        if not path:
            endpoint_mismatches.append({"edge_id": edge["edge_id"], "reason": "missing path"})
            continue
        if path[0] != STRICT_V6_DISPLAY_POINTS[edge["from_node_id"]]:
            endpoint_mismatches.append({"edge_id": edge["edge_id"], "reason": "from endpoint mismatch"})
        if path[-1] != STRICT_V6_DISPLAY_POINTS[edge["to_node_id"]]:
            endpoint_mismatches.append({"edge_id": edge["edge_id"], "reason": "to endpoint mismatch"})

    return {
        "road_policy": "Only these edge_id paths are painted. AI base prompt forbids roads.",
        "expected_edge_count": len(expected_edge_ids),
        "drawn_edge_count": len(drawn_edge_ids),
        "missing_edge_ids": sorted(expected_edge_ids - drawn_edge_ids),
        "extra_edge_ids": sorted(drawn_edge_ids - expected_edge_ids),
        "endpoint_mismatches": endpoint_mismatches,
        "visible_segment_count": len(segments),
        "intersection_count": len(intersections),
        "intersections": intersections[:20],
        "central_house_visible_segment_hits": central_hits,
        "residence_edge_central_house_visible_segment_hits": residence_central_hits,
        "passed": (
            expected_edge_ids == drawn_edge_ids
            and not endpoint_mismatches
            and len(intersections) == 0
            and central_hits == 0
        ),
    }


def collect_segments_for_audit(roads: list[dict[str, object]]) -> list[dict[str, object]]:
    segments = []
    for road in roads:
        edge_id = str(road["edge_id"])
        for segment_index, segment in enumerate(road["paint_segments"]):
            for point_index, (start, end) in enumerate(zip(segment, segment[1:])):
                segments.append(
                    {
                        "edge_id": edge_id,
                        "from_node_id": str(road["from_node_id"]),
                        "to_node_id": str(road["to_node_id"]),
                        "is_residence_edge": bool(road["is_residence_edge"]),
                        "segment_index": segment_index,
                        "point_index": point_index,
                        "start": start,
                        "end": end,
                    }
                )
    return segments


def find_intersections(segments: list[dict[str, object]]) -> list[dict[str, object]]:
    intersections = []
    for left_index, left in enumerate(segments):
        for right in segments[left_index + 1 :]:
            if left["edge_id"] == right["edge_id"]:
                continue
            if shares_endpoint(left, right):
                continue
            if segments_intersect(left["start"], left["end"], right["start"], right["end"]):
                intersections.append(
                    {
                        "edge_a": left["edge_id"],
                        "edge_b": right["edge_id"],
                        "a": [left["start"], left["end"]],
                        "b": [right["start"], right["end"]],
                    }
                )
    return intersections


def shares_endpoint(left: dict[str, object], right: dict[str, object]) -> bool:
    left_points = {left["start"], left["end"]}
    right_points = {right["start"], right["end"]}
    return bool(left_points & right_points)


def segments_intersect(
    a: tuple[int, int],
    b: tuple[int, int],
    c: tuple[int, int],
    d: tuple[int, int],
) -> bool:
    def orientation(p: tuple[int, int], q: tuple[int, int], r: tuple[int, int]) -> int:
        value = (q[1] - p[1]) * (r[0] - q[0]) - (q[0] - p[0]) * (r[1] - q[1])
        if abs(value) < 1e-9:
            return 0
        return 1 if value > 0 else 2

    o1 = orientation(a, b, c)
    o2 = orientation(a, b, d)
    o3 = orientation(c, d, a)
    o4 = orientation(c, d, b)
    return o1 != o2 and o3 != o4


def count_central_hits(
    segments: list[dict[str, object]],
    layout: dict,
    *,
    include_residence_edges: bool,
) -> int:
    central = layout.get("central_house") or {}
    if not central:
        return 0
    rect = (
        int(central["x"]),
        int(central["y"]),
        int(central["x"]) + int(central["w"]),
        int(central["y"]) + int(central["h"]),
    )
    hits = 0
    for segment in segments:
        is_residence_edge = bool(segment.get("is_residence_edge"))
        if include_residence_edges != is_residence_edge:
            continue
        start = segment["start"]
        end = segment["end"]
        if point_in_rect(start, rect) or point_in_rect(end, rect):
            hits += 1
    return hits


def save_png(image: Image.Image, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(f"{target.name}.tmp")
    temp.unlink(missing_ok=True)
    image.save(temp, "PNG", compress_level=6)
    temp.replace(target)


def save_display_webp(image: Image.Image, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    height = round(image.height * (DISPLAY_WIDTH / image.width))
    display = image.resize((DISPLAY_WIDTH, height), Image.Resampling.LANCZOS)
    temp = target.with_name(f"{target.name}.tmp")
    temp.unlink(missing_ok=True)
    display.save(temp, "WEBP", quality=92, method=6)
    temp.replace(target)


if __name__ == "__main__":
    main()
