from __future__ import annotations

import csv
import json
import unittest

from backend.witcher_larp.config import PROJECT_ROOT


LAYOUT_PATH = (
    PROJECT_ROOT
    / "data"
    / "seed"
    / "lord_map_layout.json"
)
SEED_ROOT = PROJECT_ROOT / "data" / "seed"


class LordMapLayoutContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.layout = json.loads(LAYOUT_PATH.read_text(encoding="utf-8"))
        cls.map_nodes = cls._load_csv("map_nodes.csv")
        cls.map_edges = cls._load_csv("map_edges.csv")

    def test_layout_covers_seed_nodes_and_edges(self) -> None:
        layout_nodes = set(self.layout["nodes"])
        seed_nodes = {row["node_id"] for row in self.map_nodes}
        self.assertEqual(layout_nodes, seed_nodes)

        layout_edges = set(self.layout["edges"])
        seed_edges = {row["edge_id"] for row in self.map_edges}
        self.assertEqual(layout_edges, seed_edges)

    def test_node_coordinates_and_hit_zones_stay_inside_canvas(self) -> None:
        width = int(self.layout["canvas"]["width"])
        height = int(self.layout["canvas"]["height"])

        for node_id, node in self.layout["nodes"].items():
            with self.subTest(node_id=node_id):
                self.assert_in_canvas(node["x"], node["y"], width, height)
                self.assert_in_canvas(
                    node["label_anchor"]["x"],
                    node["label_anchor"]["y"],
                    width,
                    height,
                )
                self.assert_in_canvas(
                    node["marker_anchor"]["x"],
                    node["marker_anchor"]["y"],
                    width,
                    height,
                )
                hit_zone = node["hit_zone"]
                if hit_zone["type"] == "circle":
                    self.assert_in_canvas(hit_zone["cx"], hit_zone["cy"], width, height)
                    self.assertGreater(hit_zone["r"], 0)
                elif hit_zone["type"] == "polygon":
                    self.assertGreaterEqual(len(hit_zone["points"]), 3)
                    for x, y in hit_zone["points"]:
                        self.assert_in_canvas(x, y, width, height)
                else:
                    raise AssertionError(f"Unsupported hit zone for {node_id}: {hit_zone}")

    def test_residences_are_click_targets_and_excluded_zones_are_not(self) -> None:
        central_house = self.layout["central_house"]
        house_rect = (
            central_house["x"],
            central_house["y"],
            central_house["x"] + central_house["w"],
            central_house["y"] + central_house["h"],
        )
        by_id = {row["node_id"]: row for row in self.map_nodes}
        for node_id, node in self.layout["nodes"].items():
            seed_node = by_id[node_id]
            if seed_node["node_type"] == "residence":
                self.assertTrue(node["ui_target"])
                self.assert_point_inside_rect(node["x"], node["y"], house_rect)
            elif seed_node["zone_status"] == "no_play_excluded":
                self.assertFalse(node["ui_target"])
            else:
                self.assertTrue(node["ui_target"])

    def test_ownership_sockets_exist_only_for_clickable_territories(self) -> None:
        clickable_node_ids = {
            node_id
            for node_id, node in self.layout["nodes"].items()
            if node["ui_target"]
        }
        socket_node_ids = {
            node_id
            for node_id, node in self.layout["nodes"].items()
            if "ownership_socket" in node
        }
        self.assertEqual(socket_node_ids, clickable_node_ids)
        self.assertEqual(len(socket_node_ids), 23)

        for node_id, node in self.layout["nodes"].items():
            with self.subTest(node_id=node_id):
                if node["ui_target"]:
                    self.assertIn("ownership_socket", node)
                else:
                    self.assertNotIn("ownership_socket", node)

    def test_edge_polylines_match_seed_graph_endpoints(self) -> None:
        nodes = self.layout["nodes"]
        for edge in self.map_edges:
            edge_id = edge["edge_id"]
            points = self.layout["edges"][edge_id]["points"]
            with self.subTest(edge_id=edge_id):
                self.assertGreaterEqual(len(points), 2)
                from_node = nodes[edge["from_node_id"]]
                to_node = nodes[edge["to_node_id"]]
                self.assertEqual(points[0], [from_node["x"], from_node["y"]])
                self.assertEqual(points[-1], [to_node["x"], to_node["y"]])

    def test_declared_map_art_is_decoupled_from_removed_static_panel(self) -> None:
        self.assertEqual(self.layout["art_asset"], "assets/lord-map-ai-strict-v6-roadless-base.webp")
        self.assertEqual(self.layout["road_asset"], "assets/lord-map-ai-strict-v6-baked-roads.webp")
        canvas_width = int(self.layout["canvas"]["width"])
        canvas_height = int(self.layout["canvas"]["height"])
        self.assertGreater(canvas_width, 0)
        self.assertGreater(canvas_height, 0)

    @staticmethod
    def assert_in_canvas(x: int, y: int, width: int, height: int) -> None:
        if not (0 <= int(x) <= width and 0 <= int(y) <= height):
            raise AssertionError(f"Point outside canvas: {x}, {y}")

    @staticmethod
    def assert_point_inside_rect(x: int, y: int, rect: tuple[int, int, int, int]) -> None:
        left, top, right, bottom = rect
        if not (left <= int(x) <= right and top <= int(y) <= bottom):
            raise AssertionError(f"Point outside rect: {x}, {y}, rect={rect}")

    @staticmethod
    def _load_csv(name: str) -> list[dict[str, str]]:
        with (SEED_ROOT / name).open(encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))


if __name__ == "__main__":
    unittest.main()
