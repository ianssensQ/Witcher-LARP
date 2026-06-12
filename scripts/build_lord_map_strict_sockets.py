from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = ROOT / "backend" / "witcher_larp" / "web" / "lord" / "assets"
LAYOUT_PATH = ASSET_DIR / "lord_map_layout.json"
SEED_EDGES_PATH = ROOT / "data" / "seed" / "map_edges.csv"
REPORT_DIR = ROOT / "reports" / "map-debug-crops"
DEFAULT_PREFIX = "lord_map_ai_strict_v3"
DISPLAY_WIDTH = 3172

OWNER_COLORS = {
    "node_res_north": (63, 127, 184, 238),
    "node_res_river": (201, 75, 67, 238),
    "node_res_forest": (63, 155, 96, 238),
    "node_res_hill": (211, 168, 70, 238),
}
NEUTRAL = (141, 138, 130, 235)

# Preview-space placement for the generated strict v3 artwork. The graph node
# ids stay canonical; only the visual socket centers are art-specific.
STRICT_V3_DISPLAY_OVERRIDES = {
    "node_res_north": (1295, 710),
    "node_res_river": (1585, 735),
    "node_res_forest": (1290, 920),
    "node_res_hill": (1585, 905),
    "node_fort_east": (1590, 300),
    "node_fort_west": (705, 720),
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
    "node_mountain_gray": (2020, 1080),
    "node_mountain_west_alpine": (1040, 1625),
}

STRICT_V3_EDGE_DISPLAY_PATHS = {
    "edge_north_field": [(1295, 710), (1235, 625), (1135, 560), (1015, 500)],
    "edge_north_fort_east": [(1295, 710), (1440, 585), (1590, 300)],
    "edge_fort_east_mountain_north": [(1590, 300), (1790, 315), (1990, 320), (2145, 365)],
    "edge_fort_west_field_north": [(705, 720), (825, 625), (1015, 500)],
    "edge_fort_west_field_west": [(705, 720), (610, 655), (470, 580)],
    "edge_fort_west_fort_east": [(705, 720), (900, 615), (1130, 500), (1370, 415), (1590, 300)],
    "edge_field_west_forest_dark": [(470, 580), (515, 760), (625, 985)],
    "edge_swamp_forest_west": [(580, 1190), (595, 1085), (625, 985)],
    "edge_swamp_fort_southwest": [(580, 1190), (605, 1325), (650, 1460)],
    "edge_forest_fort_southwest": [(1290, 920), (1100, 1080), (890, 1250), (705, 1385), (650, 1460)],
    "edge_fort_southwest_mountain_west": [(650, 1460), (800, 1560), (1040, 1625)],
    "edge_forest_village": [(1290, 920), (1410, 1110), (1550, 1290)],
    "edge_village_magic": [(1550, 1290), (1500, 1490), (1410, 1715)],
    "edge_village_mountain_gray": [(1550, 1290), (1760, 1195), (2020, 1080)],
    "edge_magic_science": [(1410, 1715), (1620, 1645), (1975, 1535)],
    "edge_science_forest_south": [(1975, 1535), (2110, 1545), (2285, 1555)],
    "edge_forest_south_lake_south": [(2285, 1555), (2510, 1590), (2700, 1675)],
    "edge_field_east_science": [(2630, 1260), (2440, 1370), (2210, 1480), (1975, 1535)],
    "edge_hill_field_east": [(1585, 905), (1940, 985), (2300, 1120), (2630, 1260)],
    "edge_hill_mountain": [(1585, 905), (1815, 1000), (2020, 1080)],
    "edge_village_east_well": [(2395, 850), (2330, 715), (2255, 555)],
    "edge_village_east_lake": [(2395, 850), (2485, 835), (2560, 805)],
    "edge_lake_field_east": [(2560, 805), (2570, 1010), (2630, 1260)],
    "edge_river_well": [(1585, 735), (1790, 685), (2050, 610), (2255, 555)],
    "edge_river_village_east": [(1585, 735), (1870, 780), (2180, 815), (2395, 850)],
    "edge_fort_east_well": [(1590, 300), (1800, 350), (2055, 450), (2255, 555)],
}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Draw territory ownership sockets for a strict generated lord map.",
    )
    parser.add_argument("--prefix", default=DEFAULT_PREFIX)
    parser.add_argument(
        "--input",
        type=Path,
        default=None,
        help="Full generated map PNG. Defaults to backend lord assets/<prefix>_clean_generated.png.",
    )
    parser.add_argument(
        "--transform",
        choices=("fit-preserve", "canonical"),
        default="fit-preserve",
        help="fit-preserve aligns canonical v8 sockets to the preserved 3:2 OpenRouter art inside the 9516x5952 canvas.",
    )
    args = parser.parse_args()

    prefix = args.prefix
    input_path = args.input or ASSET_DIR / f"{prefix}_clean_generated.png"
    layout = json.loads(LAYOUT_PATH.read_text(encoding="utf-8"))
    image = Image.open(input_path).convert("RGBA")

    sockets = collect_sockets(layout, image.size, args.transform, prefix)
    holes = draw_socket_rims(image.copy(), sockets, cut_holes=True)
    neutral_preview = draw_preview(image.copy(), sockets, owner_mode=False)
    owner_preview = draw_preview(image.copy(), sockets, owner_mode=True)
    graph_debug = draw_graph_debug(image.copy(), sockets, prefix)

    holes_path = ASSET_DIR / f"{prefix}_territory_sockets_holes.png"
    neutral_preview_path = ASSET_DIR / f"{prefix}_territory_sockets_neutral_preview.png"
    owner_preview_path = ASSET_DIR / f"{prefix}_territory_sockets_owner_preview.png"
    display_path = ASSET_DIR / f"{prefix}_territory_sockets_owner_preview.webp"
    holes_json_path = ASSET_DIR / f"{prefix}_territory_sockets_holes.json"
    graph_debug_path = REPORT_DIR / f"{prefix}-territory-sockets-graph-debug.webp"

    save_png(holes, holes_path)
    save_png(neutral_preview, neutral_preview_path)
    save_png(owner_preview, owner_preview_path)
    save_display_webp(owner_preview.convert("RGB"), display_path)
    save_display_webp(graph_debug.convert("RGB"), graph_debug_path)
    holes_json_path.write_text(
        json.dumps(
            {
                "asset": holes_path.name,
                "source_asset": input_path.name,
                "layout_version": layout["version"],
                "layout_mode": layout["mode"],
                "transform": args.transform,
                "placement": placement_name(prefix),
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

    update_manifest(
        prefix,
        input_path,
        holes_path,
        neutral_preview_path,
        owner_preview_path,
        display_path,
        holes_json_path,
        graph_debug_path,
    )

    print(f"holes: {holes_path}")
    print(f"neutral_preview: {neutral_preview_path}")
    print(f"owner_preview: {owner_preview_path}")
    print(f"display: {display_path}")
    print(f"holes_json: {holes_json_path}")
    print(f"graph_debug: {graph_debug_path}")


def collect_sockets(
    layout: dict[str, object],
    size: tuple[int, int],
    transform: str,
    prefix: str,
) -> list[dict[str, int | str]]:
    width, height = size
    canvas_width = int(layout["canvas"]["width"])

    # The strict OpenRouter image is 3:2 and then preserved inside the wider
    # canonical canvas. This maps v8 socket anchors to the visible generated art.
    x_scale = 1.0
    x_offset = 0.0
    y_scale = 1.0
    y_offset = 0.0
    radius_scale = 1.0
    if transform == "fit-preserve":
        raw_aspect = 3 / 2
        foreground_width = height * raw_aspect
        x_scale = foreground_width / canvas_width
        x_offset = (width - foreground_width) / 2
        radius_scale = min(x_scale, 1.0)

    sockets: list[dict[str, int | str]] = []
    for node_id, node in layout["nodes"].items():
        socket = node.get("ownership_socket")
        if not socket:
            continue
        cx = round(x_offset + float(socket["cx"]) * x_scale)
        cy = round(y_offset + float(socket["cy"]) * y_scale)
        if prefix == DEFAULT_PREFIX and node_id in STRICT_V3_DISPLAY_OVERRIDES:
            cx, cy = scale_display_point(STRICT_V3_DISPLAY_OVERRIDES[node_id], size)
        base_r = round(float(socket["r"]) * radius_scale)
        sockets.append(
            {
                "node_id": node_id,
                "cx": cx,
                "cy": cy,
                "outer_r": round(base_r * 1.23),
                "rim_r": round(base_r * 1.06),
                "hole_r": round(base_r * 0.83),
            }
        )
    return sockets


def scale_display_point(point: tuple[int, int], size: tuple[int, int]) -> tuple[int, int]:
    scale = size[0] / DISPLAY_WIDTH
    return round(point[0] * scale), round(point[1] * scale)


def placement_name(prefix: str) -> str:
    if prefix == DEFAULT_PREFIX:
        return "strict_v3_visual_territory_adjacency_v3_castle_rooms"
    return "layout_projection"


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


def draw_graph_debug(
    image: Image.Image,
    sockets: list[dict[str, int | str]],
    prefix: str,
) -> Image.Image:
    by_id = {str(socket["node_id"]): socket for socket in sockets}
    graph_layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(graph_layer)
    for edge in load_edges():
        path = graph_debug_path(edge, by_id, image.size, prefix)
        if not path:
            continue
        draw.line(path, fill=(15, 13, 9, 210), width=20, joint="curve")
        draw.line(path, fill=(87, 220, 132, 210), width=9, joint="curve")

    image.alpha_composite(graph_layer)
    return draw_preview(image, sockets, owner_mode=True)


def graph_debug_path(
    edge: dict[str, str],
    by_id: dict[str, dict[str, int | str]],
    size: tuple[int, int],
    prefix: str,
) -> list[tuple[int, int]]:
    if prefix == DEFAULT_PREFIX and edge["edge_id"] in STRICT_V3_EDGE_DISPLAY_PATHS:
        return [
            scale_display_point(point, size)
            for point in STRICT_V3_EDGE_DISPLAY_PATHS[edge["edge_id"]]
        ]

    source = by_id.get(edge["from_node_id"])
    target = by_id.get(edge["to_node_id"])
    if not source or not target:
        return []
    return [
        (int(source["cx"]), int(source["cy"])),
        (int(target["cx"]), int(target["cy"])),
    ]


def load_edges() -> list[dict[str, str]]:
    with SEED_EDGES_PATH.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def save_png(image: Image.Image, target: Path) -> None:
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


def update_manifest(
    prefix: str,
    input_path: Path,
    holes_path: Path,
    neutral_preview_path: Path,
    owner_preview_path: Path,
    display_path: Path,
    holes_json_path: Path,
    graph_debug_path: Path,
) -> None:
    manifest_path = ASSET_DIR / f"{prefix}_manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    else:
        manifest = {"prefix": prefix}
    manifest["territory_sockets"] = {
        "source_asset": str(input_path.relative_to(ROOT)).replace("\\", "/"),
        "holes_asset": str(holes_path.relative_to(ROOT)).replace("\\", "/"),
        "neutral_preview": str(neutral_preview_path.relative_to(ROOT)).replace("\\", "/"),
        "owner_preview": str(owner_preview_path.relative_to(ROOT)).replace("\\", "/"),
        "display_preview": str(display_path.relative_to(ROOT)).replace("\\", "/"),
        "holes_json": str(holes_json_path.relative_to(ROOT)).replace("\\", "/"),
        "graph_debug_preview": str(graph_debug_path.relative_to(ROOT)).replace("\\", "/"),
        "placement": placement_name(prefix),
        "note": "Transparent holes expose the owner-color underlay; preview colors use lord starts plus neutral territories.",
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
