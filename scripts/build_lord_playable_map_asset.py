from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = ROOT / "backend" / "witcher_larp" / "web" / "lord" / "assets"
SEED_DIR = ROOT / "data" / "seed"

SOURCE_ASSET = ASSET_DIR / "lord_map_generated_graph_v3_superres_6x.png"
CLEAN_SOURCE_ASSET = ASSET_DIR / "lord_map_generated_clean_v3_superres_6x.png"
TARGET_ASSET = ASSET_DIR / "lord_map_playable_v1_holes.png"
TARGET_DISPLAY_ASSET = ASSET_DIR / "lord_map_playable_v1_display.webp"
TARGET_PREVIEW = ASSET_DIR / "lord_map_playable_v1_holes_preview.png"
TARGET_HOLES = ASSET_DIR / "lord_map_playable_v1_holes.json"
TARGET_LAYOUT = ASSET_DIR / "lord_map_layout.json"

SOURCE_SCALE = 6
SOCKET_RADIUS_SOURCE = 17.0
EXCLUDED_REPAIR_RADIUS_SOURCE = 26.0
EXCLUDED_REPAIR_FEATHER_SOURCE = 8.0
DISPLAY_WIDTH = 3172
EXCLUDED_REPAIR_OFFSETS_SOURCE = {
    "node_old_house": (75.0, 0.0),
    "node_adjacent_shed": (72.5, -22.5),
}
EXTRA_REPAIR_SPOTS_SOURCE = (
    ((270.0, 338.0), (75.0, 0.0)),
    ((1170.0, 479.0), (75.0, 0.0)),
)
CLEAN_RESTORE_SPOTS_SOURCE = (
    (742.0, 408.0),
    (850.0, 408.0),
    (742.0, 512.0),
    (850.0, 512.0),
    (801.0, 484.0),
    (911.22, 393.97),
    (477.37, 529.29),
    (1020.83, 445.83),
)


# Coordinates are in the generated 1586x992 source map space. The final layout
# stores upscaled image pixels so the SVG, hit zones and transparent holes share
# exactly one coordinate system.
NODE_SOURCE_COORDS: dict[str, tuple[float, float]] = {
    "node_res_north": (706.56, 407.71),
    "node_res_river": (811.24, 388.37),
    "node_res_forest": (711.20, 477.65),
    "node_res_hill": (888.16, 484.59),
    "node_fort_east": (759.94, 211.55),
    "node_fort_west": (330.18, 432.50),
    "node_fort_southwest": (587.28, 621.92),
    "node_field_oats": (476.77, 270.15),
    "node_field_west_large": (186.36, 234.61),
    "node_field_east_large": (1163.01, 598.47),
    "node_village_barn": (819.73, 648.14),
    "node_village_east_shed": (1183.33, 450.0),
    "node_well_city": (1125.25, 281.09),
    "node_spanish_magic": (815.91, 937.14),
    "node_science_barn": (964.94, 855.17),
    "node_forest_dark": (219.76, 825.38),
    "node_forest_south_garden": (1488.82, 843.28),
    "node_lake_mist": (1284.62, 399.64),
    "node_lake_south_pond": (1380.98, 938.57),
    "node_swamp_black": (268.87, 696.19),
    "node_mountain_north_alpine": (980.0, 220.0),
    "node_mountain_gray": (983.33, 553.33),
    "node_mountain_west_alpine": (705.78, 848.50),
    "node_old_house": (212.08, 194.98),
    "node_adjacent_shed": (925.0, 450.0),
}

CUSTOM_EDGE_WAYPOINTS: dict[str, list[tuple[int, int]]] = {
    "edge_fort_west_fort_east": [(1700, 900), (3500, 350), (4500, 850)],
    "edge_north_fort_east": [(4400, 1900)],
    "edge_river_well": [(5600, 1850), (6400, 1650)],
    "edge_village_east_well": [(7050, 2200), (6900, 1900)],
    "edge_river_village_east": [(5600, 2500), (6900, 2500)],
    "edge_hill_field_east": [(6200, 2600), (7200, 3000)],
    "edge_village_east_lake": [(7350, 2600)],
    "edge_hill_mountain": [(5600, 3100)],
    "edge_village_mountain_gray": [(5400, 3850)],
    "edge_fort_east_well": [(5200, 1100), (6500, 1300)],
    "edge_field_east_science": [(6750, 4300), (6200, 4900)],
    "edge_lake_field_east": [(7600, 3100), (7250, 3400)],
}

LABEL_OFFSETS_SOURCE: dict[str, tuple[float, float]] = {
    "node_res_north": (0, -26),
    "node_res_river": (0, -26),
    "node_res_forest": (0, 42),
    "node_res_hill": (0, 42),
    "node_forest_dark": (0, 44),
    "node_forest_south_garden": (-30, -44),
    "node_lake_south_pond": (0, -44),
    "node_spanish_magic": (0, -44),
    "node_science_barn": (0, -44),
    "node_swamp_black": (0, -42),
    "node_field_east_large": (0, -42),
    "node_old_house": (0, -38),
    "node_adjacent_shed": (40, 30),
}


def load_csv(name: str) -> list[dict[str, str]]:
    with (SEED_DIR / name).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def scaled_point(node_id: str) -> tuple[int, int]:
    x, y = NODE_SOURCE_COORDS[node_id]
    return round(x * SOURCE_SCALE), round(y * SOURCE_SCALE)


def scaled_radius(source_radius: float) -> int:
    return round(source_radius * SOURCE_SCALE)


def node_layer(row: dict[str, str]) -> str:
    if row["node_type"] == "residence":
        return "residence"
    if row["zone_status"] == "no_play_excluded":
        return "excluded"
    return "territory"


def label_anchor(node_id: str, x: int, y: int) -> dict[str, int]:
    dx, dy = LABEL_OFFSETS_SOURCE.get(node_id, (0, -36))
    return {
        "x": x + round(dx * SOURCE_SCALE),
        "y": y + round(dy * SOURCE_SCALE),
    }


def build_nodes(map_nodes: list[dict[str, str]]) -> dict[str, dict[str, object]]:
    nodes: dict[str, dict[str, object]] = {}
    for row in map_nodes:
        node_id = row["node_id"]
        x, y = scaled_point(node_id)
        layer = node_layer(row)
        ui_target = layer != "excluded"
        hit_radius = scaled_radius(24 if ui_target else 20)
        node: dict[str, object] = {
            "x": x,
            "y": y,
            "label_anchor": label_anchor(node_id, x, y),
            "marker_anchor": {"x": x, "y": y - scaled_radius(4)},
            "hit_zone": {"type": "circle", "cx": x, "cy": y, "r": hit_radius},
            "ui_target": ui_target,
            "layer": layer,
        }
        if ui_target:
            node["ownership_socket"] = {
                "cx": x,
                "cy": y,
                "r": scaled_radius(SOCKET_RADIUS_SOURCE),
            }
        nodes[node_id] = node
    return nodes


def build_edges(
    map_edges: list[dict[str, str]], nodes: dict[str, dict[str, object]]
) -> dict[str, dict[str, list[list[int]]]]:
    edges: dict[str, dict[str, list[list[int]]]] = {}
    for index, edge in enumerate(map_edges):
        from_node = nodes[edge["from_node_id"]]
        to_node = nodes[edge["to_node_id"]]
        x1, y1 = int(from_node["x"]), int(from_node["y"])
        x2, y2 = int(to_node["x"]), int(to_node["y"])
        custom_waypoints = CUSTOM_EDGE_WAYPOINTS.get(edge["edge_id"])
        if custom_waypoints is not None:
            edges[edge["edge_id"]] = {
                "points": [[x1, y1], *([x, y] for x, y in custom_waypoints), [x2, y2]]
            }
            continue
        dx = x2 - x1
        dy = y2 - y1
        distance = max(1.0, (dx * dx + dy * dy) ** 0.5)
        bend = min(320, distance * 0.10) * (-1 if index % 2 else 1)
        mid_x = round((x1 + x2) / 2 - dy / distance * bend)
        mid_y = round((y1 + y2) / 2 + dx / distance * bend)
        edges[edge["edge_id"]] = {"points": [[x1, y1], [mid_x, mid_y], [x2, y2]]}
    return edges


def cut_holes(
    source: Path,
    target: Path,
    preview: Path,
    nodes: dict[str, dict[str, object]],
) -> list[dict[str, object]]:
    image = Image.open(source).convert("RGBA")
    image = repair_excluded_sockets(image, nodes)
    write_display_asset(image, TARGET_DISPLAY_ASSET)
    alpha = np.asarray(image.getchannel("A"), dtype=np.uint8).copy()
    height, width = alpha.shape
    yy, xx = np.ogrid[:height, :width]
    holes: list[dict[str, object]] = []

    for node_id, node in nodes.items():
        socket = node.get("ownership_socket")
        if not socket:
            continue
        cx = float(socket["cx"])
        cy = float(socket["cy"])
        radius = float(socket["r"]) * 0.92
        feather = 8.0
        distance = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
        inner = distance <= radius
        edge = (distance > radius) & (distance <= radius + feather)
        alpha[inner] = 0
        if np.any(edge):
            falloff = ((distance[edge] - radius) / feather * 255).astype(np.uint8)
            alpha[edge] = np.minimum(alpha[edge], falloff)
        holes.append(
            {
                "node_id": node_id,
                "cx": round(cx),
                "cy": round(cy),
                "radius": round(radius),
            }
        )

    image.putalpha(Image.fromarray(alpha, mode="L"))
    image.save(target, optimize=True)

    underlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    color_cycle = [
        (174, 47, 52, 255),
        (61, 123, 195, 255),
        (62, 151, 91, 255),
        (190, 143, 47, 255),
    ]
    from PIL import ImageDraw

    draw = ImageDraw.Draw(underlay)
    for index, hole in enumerate(holes):
        radius = int(hole["radius"]) + 8
        cx = int(hole["cx"])
        cy = int(hole["cy"])
        draw.ellipse(
            (cx - radius, cy - radius, cx + radius, cy + radius),
            fill=color_cycle[index % len(color_cycle)],
        )
    Image.alpha_composite(underlay, image).save(preview, optimize=True)
    return holes


def repair_excluded_sockets(
    image: Image.Image,
    nodes: dict[str, dict[str, object]],
) -> Image.Image:
    source = image.copy()
    result = image.copy()
    clean_source = Image.open(CLEAN_SOURCE_ASSET).convert("RGBA")

    for node_id, node in nodes.items():
        if node.get("layer") != "excluded":
            continue
        dx_source, dy_source = EXCLUDED_REPAIR_OFFSETS_SOURCE.get(node_id, (75.0, 0.0))
        paste_repaired_socket(
            result,
            source,
            int(node["x"]),
            int(node["y"]),
            dx_source,
            dy_source,
        )

    for (cx_source, cy_source), (dx_source, dy_source) in EXTRA_REPAIR_SPOTS_SOURCE:
        paste_repaired_socket(
            result,
            source,
            round(cx_source * SOURCE_SCALE),
            round(cy_source * SOURCE_SCALE),
            dx_source,
            dy_source,
        )

    for cx_source, cy_source in CLEAN_RESTORE_SPOTS_SOURCE:
        paste_restored_socket(
            result,
            clean_source,
            round(cx_source * SOURCE_SCALE),
            round(cy_source * SOURCE_SCALE),
        )

    return result


def paste_repaired_socket(
    result: Image.Image,
    source: Image.Image,
    cx: int,
    cy: int,
    dx_source: float,
    dy_source: float,
) -> None:
    radius = scaled_radius(EXCLUDED_REPAIR_RADIUS_SOURCE)
    feather = scaled_radius(EXCLUDED_REPAIR_FEATHER_SOURCE)
    outer = radius + feather
    dx = round(dx_source * SOURCE_SCALE)
    dy = round(dy_source * SOURCE_SCALE)
    left = cx - outer
    top = cy - outer
    box = (left, top, cx + outer, cy + outer)
    source_box = (left + dx, top + dy, cx + outer + dx, cy + outer + dy)
    if (
        source_box[0] < 0
        or source_box[1] < 0
        or source_box[2] > source.width
        or source_box[3] > source.height
    ):
        return

    patch = source.crop(source_box)
    mask = Image.new("L", patch.size, 0)
    draw = ImageDraw.Draw(mask)
    inset = feather // 2
    draw.ellipse(
        (inset, inset, patch.width - inset - 1, patch.height - inset - 1),
        fill=255,
    )
    mask = mask.filter(ImageFilter.GaussianBlur(feather / 2))
    result.paste(patch, box[:2], mask)


def paste_restored_socket(
    result: Image.Image,
    source: Image.Image,
    cx: int,
    cy: int,
) -> None:
    radius = scaled_radius(32.0)
    feather = scaled_radius(10.0)
    outer = radius + feather
    left = cx - outer
    top = cy - outer
    box = (left, top, cx + outer, cy + outer)
    if box[0] < 0 or box[1] < 0 or box[2] > source.width or box[3] > source.height:
        return

    patch = source.crop(box)
    mask = Image.new("L", patch.size, 0)
    draw = ImageDraw.Draw(mask)
    inset = feather // 2
    draw.ellipse(
        (inset, inset, patch.width - inset - 1, patch.height - inset - 1),
        fill=255,
    )
    mask = mask.filter(ImageFilter.GaussianBlur(feather / 2))
    result.paste(patch, box[:2], mask)


def write_display_asset(image: Image.Image, target: Path) -> None:
    width = min(DISPLAY_WIDTH, image.width)
    height = round(image.height * (width / image.width))
    display = image.convert("RGB").resize((width, height), Image.Resampling.LANCZOS)
    display.save(target, "WEBP", quality=82, method=6)


def build_layout(
    image_size: tuple[int, int],
    nodes: dict[str, dict[str, object]],
    edges: dict[str, dict[str, list[list[int]]]],
) -> dict[str, object]:
    width, height = image_size
    return {
        "layout_id": "venue_map_v3_playable_holes",
        "version": 8,
        "mode": "sparse_graph_v0_3_planar_no_castle_cut",
        "art_asset": "assets/lord_map_playable_v1_display.webp",
        "future_art_asset": "assets/lord_map_playable_v1_display.webp",
        "canvas": {"width": width, "height": height},
        "viewport": {
            "default_x": 0.50,
            "default_y": 0.54,
            "mobile_zoom": 0.48,
            "desktop_zoom": 0.58,
            "min_zoom": 0.36,
            "max_zoom": 1.0,
        },
        "visibility": {
            "graph_visible": True,
            "territory_owner_visible": True,
            "svg_edges_visible": False,
            "svg_node_markers_visible": False,
            "central_house_overlay_visible": False,
            "socket_rims_visible": True,
            "enemy_army_policy": "hidden_until_intel",
            "enemy_garrison_policy": "details_hidden_until_intel",
        },
        "central_house": {
            "id": "central_active_house",
            "x": round(642 * SOURCE_SCALE),
            "y": round(350 * SOURCE_SCALE),
            "w": round(310 * SOURCE_SCALE),
            "h": round(230 * SOURCE_SCALE),
            "ui_target": False,
            "note": "Lord residences are rooms inside this house; the house is not capturable.",
        },
        "nodes": nodes,
        "edges": edges,
    }


def main() -> None:
    map_nodes = load_csv("map_nodes.csv")
    map_edges = load_csv("map_edges.csv")
    nodes = build_nodes(map_nodes)
    edges = build_edges(map_edges, nodes)
    image_size = Image.open(SOURCE_ASSET).size
    holes = cut_holes(SOURCE_ASSET, TARGET_ASSET, TARGET_PREVIEW, nodes)
    layout = build_layout(image_size, nodes, edges)

    TARGET_HOLES.write_text(
        json.dumps({"asset": TARGET_ASSET.name, "holes": holes}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    TARGET_LAYOUT.write_text(json.dumps(layout, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"layout: {TARGET_LAYOUT}")
    print(f"asset: {TARGET_ASSET} {image_size[0]}x{image_size[1]}")
    print(f"holes: {len(holes)}")


if __name__ == "__main__":
    main()
