from __future__ import annotations

import argparse
import json
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = ROOT / "backend" / "witcher_larp" / "web" / "lord" / "assets"


def luminance(rgb: np.ndarray) -> np.ndarray:
    return (
        rgb[:, :, 0].astype(np.float32) * 0.2126
        + rgb[:, :, 1].astype(np.float32) * 0.7152
        + rgb[:, :, 2].astype(np.float32) * 0.0722
    )


def find_dark_socket_centers(image: Image.Image) -> list[dict[str, float]]:
    rgb = np.asarray(image.convert("RGB"))
    lum = luminance(rgb)
    # The node sockets have very dark circular centers. Roads and terrain are
    # darker too, so component shape and size do the real filtering below.
    dark = lum < 48
    height, width = dark.shape
    seen = np.zeros_like(dark, dtype=bool)
    sockets: list[dict[str, float]] = []

    for y in range(height):
        for x in range(width):
            if seen[y, x] or not dark[y, x]:
                continue

            queue: deque[tuple[int, int]] = deque([(x, y)])
            seen[y, x] = True
            xs: list[int] = []
            ys: list[int] = []

            while queue:
                cx, cy = queue.popleft()
                xs.append(cx)
                ys.append(cy)

                for nx, ny in (
                    (cx - 1, cy),
                    (cx + 1, cy),
                    (cx, cy - 1),
                    (cx, cy + 1),
                ):
                    if (
                        0 <= nx < width
                        and 0 <= ny < height
                        and not seen[ny, nx]
                        and dark[ny, nx]
                    ):
                        seen[ny, nx] = True
                        queue.append((nx, ny))

            area = len(xs)
            if area < 120 or area > 1200:
                continue

            min_x, max_x = min(xs), max(xs)
            min_y, max_y = min(ys), max(ys)
            box_w = max_x - min_x + 1
            box_h = max_y - min_y + 1
            if box_w < 16 or box_h < 16 or box_w > 44 or box_h > 44:
                continue

            aspect = box_w / box_h
            fill = area / (box_w * box_h)
            if not 0.72 <= aspect <= 1.28 or fill < 0.48:
                continue

            center_x = float(sum(xs) / area)
            center_y = float(sum(ys) / area)
            radius = float(max(box_w, box_h) / 2 + 1.2)
            sockets.append(
                {
                    "x": round(center_x, 2),
                    "y": round(center_y, 2),
                    "radius": round(radius, 2),
                    "area": area,
                }
            )

    sockets.sort(key=lambda item: (item["y"], item["x"]))
    return sockets


def upscale_map(source: Path, target: Path, scale: int) -> Image.Image:
    image = Image.open(source).convert("RGBA")
    size = (image.width * scale, image.height * scale)
    upscaled = image.resize(size, Image.Resampling.LANCZOS)
    upscaled = ImageEnhance.Contrast(upscaled).enhance(1.07)
    upscaled = ImageEnhance.Sharpness(upscaled).enhance(1.25)
    upscaled = upscaled.filter(
        ImageFilter.UnsharpMask(radius=1.35, percent=185, threshold=2)
    )
    upscaled.save(target, optimize=True)
    return upscaled


def cut_socket_holes(
    image: Image.Image, sockets: list[dict[str, float]], target: Path, scale: int
) -> Image.Image:
    result = image.convert("RGBA")
    alpha = result.getchannel("A")
    alpha_np = np.asarray(alpha, dtype=np.uint8).copy()
    height, width = alpha_np.shape
    yy, xx = np.ogrid[:height, :width]

    for socket in sockets:
        cx = socket["x"] * scale
        cy = socket["y"] * scale
        # Cut the dark center and a tiny anti-aliased edge, while keeping the
        # decorative pale rim from the generated map.
        radius = socket["radius"] * scale * 0.92
        feather = max(2.0, scale * 1.3)
        distance = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
        inner = distance <= radius
        edge = (distance > radius) & (distance <= radius + feather)
        alpha_np[inner] = 0
        if np.any(edge):
            falloff = ((distance[edge] - radius) / feather * 255).astype(np.uint8)
            alpha_np[edge] = np.minimum(alpha_np[edge], falloff)

    result.putalpha(Image.fromarray(alpha_np, mode="L"))
    result.save(target, optimize=True)
    return result


def create_hole_preview(
    image_with_holes: Image.Image,
    sockets: list[dict[str, float]],
    target: Path,
    scale: int,
) -> None:
    underlay = Image.new("RGBA", image_with_holes.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(underlay)
    colors = [
        (181, 49, 52, 255),
        (64, 118, 189, 255),
        (53, 143, 86, 255),
        (181, 137, 45, 255),
    ]
    for index, socket in enumerate(sockets):
        cx = socket["x"] * scale
        cy = socket["y"] * scale
        radius = socket["radius"] * scale * 1.02
        color = colors[index % len(colors)]
        draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=color)

    preview = Image.alpha_composite(underlay, image_with_holes)
    preview.save(target, optimize=True)


def write_holes_json(
    sockets: list[dict[str, float]], target: Path, source_size: tuple[int, int], scale: int
) -> None:
    payload = {
        "sourceSize": {"width": source_size[0], "height": source_size[1]},
        "upscaledSize": {"width": source_size[0] * scale, "height": source_size[1] * scale},
        "scale": scale,
        "holes": [
            {
                "sourceX": socket["x"],
                "sourceY": socket["y"],
                "sourceRadius": socket["radius"],
                "upscaledX": round(socket["x"] * scale, 2),
                "upscaledY": round(socket["y"] * scale, 2),
                "upscaledRadius": round(socket["radius"] * scale * 0.92, 2),
            }
            for socket in sockets
        ],
    }
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scale", type=int, default=6)
    args = parser.parse_args()

    clean_source = ASSET_DIR / "lord_map_generated_clean_v2_source.png"
    graph_source = ASSET_DIR / "lord_map_generated_graph_v2_source.png"
    clean_target = ASSET_DIR / "lord_map_generated_clean_v3_superres_6x.png"
    graph_target = ASSET_DIR / "lord_map_generated_graph_v3_superres_6x.png"
    holes_target = ASSET_DIR / "lord_map_generated_graph_v3_superres_6x_holes.png"
    preview_target = ASSET_DIR / "lord_map_generated_graph_v3_superres_6x_holes_preview.png"
    holes_json = ASSET_DIR / "lord_map_generated_graph_v3_holes.json"

    clean = upscale_map(clean_source, clean_target, args.scale)
    graph_source_image = Image.open(graph_source).convert("RGBA")
    sockets = find_dark_socket_centers(graph_source_image)
    graph = upscale_map(graph_source, graph_target, args.scale)
    graph_holes = cut_socket_holes(graph, sockets, holes_target, args.scale)
    create_hole_preview(graph_holes, sockets, preview_target, args.scale)
    write_holes_json(sockets, holes_json, graph_source_image.size, args.scale)

    print(f"clean: {clean_target} {clean.width}x{clean.height}")
    print(f"graph: {graph_target} {graph.width}x{graph.height}")
    print(f"holes: {holes_target} {graph_holes.width}x{graph_holes.height}")
    print(f"preview: {preview_target}")
    print(f"holes_json: {holes_json}")
    print(f"detected_holes: {len(sockets)}")


if __name__ == "__main__":
    main()
