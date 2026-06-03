from __future__ import annotations

import unittest
from uuid import uuid4

from backend.witcher_larp.asset_service import grant_asset_ownership
from backend.witcher_larp.config import PROJECT_ROOT, Settings
from backend.witcher_larp.database import connect
from backend.witcher_larp.import_service import import_seed_pack
from backend.witcher_larp.sorceress_service import accept_trade_transfer, buy_potion
from backend.witcher_larp.sorceress_service import create_trade_transfer, decline_trade_transfer
from backend.witcher_larp.sorceress_service import ensure_sorceress_runtime_state


TEST_TMP_ROOT = PROJECT_ROOT / ".test-data"
FIXTURE_MANIFEST = PROJECT_ROOT / "tests" / "fixtures" / "seed_valid" / "fixture_manifest.csv"


class TradeTransferContractTests(unittest.TestCase):
    def setUp(self) -> None:
        TEST_TMP_ROOT.mkdir(exist_ok=True)

    def test_accept_moves_item_and_artifact_to_exactly_one_owner(self) -> None:
        settings = self.prepare_seed("trade_accept_generic")
        with connect(settings) as connection:
            grant_asset_ownership(
                connection,
                owner_player_id="p_witcher_1",
                asset_type="item",
                asset_id="item_silver_dust",
                source="test_seed",
                source_ref_id="owned_item",
            )
            grant_asset_ownership(
                connection,
                owner_player_id="p_witcher_1",
                asset_type="artifact",
                asset_id="artifact_mirror_shard",
                source="test_seed",
                source_ref_id="owned_artifact",
            )

            item_transfer = create_trade_transfer(
                connection,
                transfer_id="trade_item_accept",
                from_player_id="p_witcher_1",
                to_player_id="p_witcher_2",
                asset_type="item",
                asset_id="item_silver_dust",
            )
            artifact_transfer = create_trade_transfer(
                connection,
                transfer_id="trade_artifact_accept",
                from_player_id="p_witcher_1",
                to_player_id="p_sorc_1",
                asset_type="artifact",
                asset_id="artifact_mirror_shard",
            )
            item_accepted = accept_trade_transfer(
                connection,
                item_transfer["transfer_id"],
                accepted_by_player_id="p_witcher_2",
            )
            artifact_accepted = accept_trade_transfer(
                connection,
                artifact_transfer["transfer_id"],
                accepted_by_player_id="p_sorc_1",
            )

            item_owners = self.owners(connection, "item", "item_silver_dust")
            artifact_owners = self.owners(connection, "artifact", "artifact_mirror_shard")
            active_locks = self.active_lock_count(connection)

        self.assertEqual(item_accepted["status"], "accepted")
        self.assertEqual(artifact_accepted["status"], "accepted")
        self.assertEqual(item_owners, {"p_witcher_2": 1})
        self.assertEqual(artifact_owners, {"p_sorc_1": 1})
        self.assertEqual(active_locks, 1)

    def test_decline_releases_card_lock_back_to_original_owner(self) -> None:
        settings = self.prepare_seed("trade_decline_card")
        with connect(settings) as connection:
            grant_asset_ownership(
                connection,
                owner_player_id="p_witcher_1",
                asset_type="card",
                asset_id="pc_cavalry_t2",
                source="test_seed",
                source_ref_id="owned_card",
            )
            created = create_trade_transfer(
                connection,
                transfer_id="trade_card_decline",
                from_player_id="p_witcher_1",
                to_player_id="p_lord_1",
                asset_type="card",
                asset_id="pc_cavalry_t2",
            )
            owner_after_create = self.owners(connection, "card", "pc_cavalry_t2")
            active_after_create = self.active_lock_count(connection)
            declined = decline_trade_transfer(
                connection,
                created["transfer_id"],
                declined_by_player_id="p_lord_1",
                reason="lord refused the writ",
            )
            owner_after_decline = self.owners(connection, "card", "pc_cavalry_t2")
            active_after_decline = self.active_lock_count(connection)

        self.assertEqual(created["status"], "pending_locked")
        self.assertEqual(owner_after_create, {})
        self.assertEqual(active_after_create, 2)
        self.assertEqual(declined["status"], "declined")
        self.assertEqual(owner_after_decline, {"p_witcher_1": 1})
        self.assertEqual(active_after_decline, 1)

    def test_potion_transfer_uses_generic_flow_without_breaking_inventory(self) -> None:
        settings = self.prepare_seed("trade_potion")
        with connect(settings) as connection:
            buy_potion(
                connection,
                buyer_id="p_sorc_1",
                potion_id="potion_common_swallow",
                quantity=2,
            )
            created = create_trade_transfer(
                connection,
                transfer_id="trade_potion_accept",
                from_player_id="p_sorc_1",
                to_player_id="p_witcher_1",
                asset_type="potion",
                asset_id="potion_common_swallow",
                quantity=1,
            )
            sorc_after_create = self.potion_quantity(
                connection,
                "p_sorc_1",
                "potion_common_swallow",
            )
            accepted = accept_trade_transfer(
                connection,
                created["transfer_id"],
                accepted_by_player_id="p_witcher_1",
            )
            sorc_after_accept = self.potion_quantity(
                connection,
                "p_sorc_1",
                "potion_common_swallow",
            )
            witcher_after_accept = self.potion_quantity(
                connection,
                "p_witcher_1",
                "potion_common_swallow",
            )

        self.assertEqual(created["status"], "pending_locked")
        self.assertEqual(sorc_after_create, 1)
        self.assertEqual(accepted["status"], "accepted")
        self.assertEqual(sorc_after_accept, 1)
        self.assertEqual(witcher_after_accept, 2)

    def test_trade_accept_is_idempotent_and_accepted_transfer_cannot_be_declined(self) -> None:
        settings = self.prepare_seed("trade_terminal_states")
        with connect(settings) as connection:
            grant_asset_ownership(
                connection,
                owner_player_id="p_witcher_1",
                asset_type="item",
                asset_id="item_herb_bundle",
                source="test_seed",
                source_ref_id="owned_herb",
            )
            created = create_trade_transfer(
                connection,
                transfer_id="trade_terminal_accept",
                from_player_id="p_witcher_1",
                to_player_id="p_witcher_2",
                asset_type="item",
                asset_id="item_herb_bundle",
            )
            accepted = accept_trade_transfer(
                connection,
                created["transfer_id"],
                accepted_by_player_id="p_witcher_2",
            )
            duplicate = accept_trade_transfer(
                connection,
                created["transfer_id"],
                accepted_by_player_id="p_witcher_2",
            )
            with self.assertRaisesRegex(Exception, "Accepted transfers cannot be declined"):
                decline_trade_transfer(
                    connection,
                    created["transfer_id"],
                    declined_by_player_id="p_witcher_2",
                )
            owners = self.owners(connection, "item", "item_herb_bundle")
            active_locks = self.active_lock_count(connection)

        self.assertEqual(accepted["status"], "accepted")
        self.assertFalse(accepted["duplicate"])
        self.assertEqual(duplicate["status"], "accepted")
        self.assertTrue(duplicate["duplicate"])
        self.assertEqual(owners, {"p_witcher_2": 1})
        self.assertEqual(active_locks, 1)

    def test_seed_pending_trade_import_creates_asset_lock_and_audit(self) -> None:
        settings = self.prepare_seed("trade_seed_pending_lock")
        with connect(settings) as connection:
            ensure_sorceress_runtime_state(connection)

            with self.assertRaisesRegex(Exception, "locked"):
                create_trade_transfer(
                    connection,
                    transfer_id="trade_seed_lock_reuse",
                    from_player_id="p_witcher_1",
                    to_player_id="p_witcher_2",
                    asset_type="item",
                    asset_id="item_monster_trophy",
                )

            lock = connection.execute(
                """
                SELECT lock_type, source_ref_id, owner_player_id, asset_type, asset_id, status
                FROM asset_locks
                WHERE source_ref_id = 'trade_pending_trophy'
                  AND status = 'active'
                """
            ).fetchone()
            audit_count = connection.execute(
                """
                SELECT COUNT(*)
                FROM event_log
                WHERE event_type = 'trade_transfer_seed_lock_created'
                  AND payload_json LIKE '%trade_pending_trophy%'
                """
            ).fetchone()[0]

        self.assertIsNotNone(lock)
        self.assertEqual(lock["lock_type"], "trade_transfer")
        self.assertEqual(lock["owner_player_id"], "p_witcher_1")
        self.assertEqual(lock["asset_type"], "item")
        self.assertEqual(lock["asset_id"], "item_monster_trophy")
        self.assertEqual(audit_count, 1)

    def test_seed_accepted_potion_transfer_applies_inventory_once(self) -> None:
        settings = self.prepare_seed("trade_seed_accepted_potion")
        with connect(settings) as connection:
            ensure_sorceress_runtime_state(connection)
            ensure_sorceress_runtime_state(connection)

            target_quantity = self.potion_quantity(
                connection,
                "p_witcher_1",
                "potion_common_swallow",
            )
            audit_count = connection.execute(
                """
                SELECT COUNT(*)
                FROM event_log
                WHERE event_type = 'trade_transfer_seed_effect_applied'
                  AND payload_json LIKE '%trade_accepted_potion%'
                """
            ).fetchone()[0]

        self.assertEqual(target_quantity, 1)
        self.assertEqual(audit_count, 1)

    def prepare_seed(self, name: str) -> Settings:
        settings = Settings(database_path=TEST_TMP_ROOT / f"{name}_{uuid4().hex}.db")
        report = import_seed_pack(settings, manifest_path=FIXTURE_MANIFEST, snapshot_dir=None)
        self.assertEqual(report.status, "success")
        return settings

    @staticmethod
    def owners(connection, asset_type: str, asset_id: str) -> dict[str, int]:
        return {
            row["owner_player_id"]: int(row["quantity"])
            for row in connection.execute(
                """
                SELECT owner_player_id, quantity
                FROM asset_ownership
                WHERE asset_type = ?
                  AND asset_id = ?
                  AND status = 'active'
                ORDER BY owner_player_id
                """,
                (asset_type, asset_id),
            ).fetchall()
        }

    @staticmethod
    def potion_quantity(connection, player_id: str, potion_id: str) -> int:
        row = connection.execute(
            """
            SELECT quantity
            FROM potion_inventory
            WHERE player_id = ? AND potion_id = ?
            """,
            (player_id, potion_id),
        ).fetchone()
        return int(row["quantity"]) if row is not None else 0

    @staticmethod
    def active_lock_count(connection) -> int:
        return int(
            connection.execute(
                "SELECT COUNT(*) FROM asset_locks WHERE status = 'active'"
            ).fetchone()[0]
        )


if __name__ == "__main__":
    unittest.main()
