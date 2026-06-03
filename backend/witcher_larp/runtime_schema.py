"""Runtime SQLite schema for mutable game state."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from typing import Any


def ensure_runtime_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS act_state (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            current_act_id TEXT,
            status TEXT NOT NULL DEFAULT 'not_started',
            active_started_at TEXT,
            final_locked_at TEXT,
            updated_at TEXT NOT NULL
        );

        INSERT INTO act_state (id, status, updated_at)
        VALUES (1, 'not_started', CURRENT_TIMESTAMP)
        ON CONFLICT(id) DO NOTHING;

        CREATE TABLE IF NOT EXISTS act_history (
            act_id TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            started_at TEXT NOT NULL,
            completed_at TEXT,
            operator TEXT NOT NULL,
            source TEXT NOT NULL,
            physical_announcement_state TEXT NOT NULL,
            physical_announcement_at TEXT,
            unlock_revealed_at TEXT,
            unlock_revealed_by TEXT,
            server_timestamp TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS player_runtime_state (
            player_id TEXT PRIMARY KEY,
            role_type TEXT NOT NULL,
            level INTEGER NOT NULL,
            xp INTEGER NOT NULL DEFAULT 0,
            gold INTEGER NOT NULL DEFAULT 0,
            stats_json TEXT NOT NULL DEFAULT '{}',
            mana INTEGER NOT NULL DEFAULT 0,
            max_mana INTEGER NOT NULL DEFAULT 0,
            challenge_tokens INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS reputation_state (
            player_id TEXT PRIMARY KEY,
            role_type TEXT NOT NULL,
            value INTEGER NOT NULL DEFAULT 0,
            label TEXT NOT NULL,
            player_descriptor TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS reputation_changes (
            change_id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id TEXT NOT NULL,
            delta INTEGER NOT NULL,
            value_before INTEGER NOT NULL,
            value_after INTEGER NOT NULL,
            label_after TEXT NOT NULL,
            player_descriptor_after TEXT NOT NULL,
            reason TEXT NOT NULL,
            visibility TEXT NOT NULL,
            source TEXT NOT NULL,
            source_event_id INTEGER,
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_reputation_changes_player
        ON reputation_changes(player_id, created_at);

        CREATE TABLE IF NOT EXISTS npc_runtime_events (
            npc_runtime_event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            npc_event_id TEXT,
            npc_role TEXT NOT NULL,
            event_type TEXT NOT NULL,
            target_scope TEXT NOT NULL,
            target_ids_json TEXT NOT NULL DEFAULT '[]',
            price_json TEXT NOT NULL DEFAULT '{}',
            condition_json TEXT NOT NULL DEFAULT '{}',
            consequence_json TEXT NOT NULL DEFAULT '{}',
            reputation_delta INTEGER NOT NULL DEFAULT 0,
            visibility TEXT NOT NULL,
            severity TEXT NOT NULL,
            severity_meaning TEXT NOT NULL,
            review_route TEXT NOT NULL,
            review_owner TEXT NOT NULL,
            blocks_progress INTEGER NOT NULL DEFAULT 0,
            final_flag INTEGER NOT NULL DEFAULT 0,
            operator TEXT NOT NULL,
            source TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_npc_runtime_events_severity
        ON npc_runtime_events(severity, created_at);

        CREATE TABLE IF NOT EXISTS npc_deals (
            deal_id INTEGER PRIMARY KEY AUTOINCREMENT,
            npc_runtime_event_id INTEGER NOT NULL,
            npc_role TEXT NOT NULL,
            target_ids_json TEXT NOT NULL DEFAULT '[]',
            price_json TEXT NOT NULL DEFAULT '{}',
            condition_json TEXT NOT NULL DEFAULT '{}',
            consequence_json TEXT NOT NULL DEFAULT '{}',
            final_flag INTEGER NOT NULL DEFAULT 0,
            hidden_price INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'captured',
            created_at TEXT NOT NULL,
            FOREIGN KEY (npc_runtime_event_id) REFERENCES npc_runtime_events(npc_runtime_event_id)
        );

        CREATE TABLE IF NOT EXISTS pve_attempts (
            pve_attempt_id INTEGER PRIMARY KEY AUTOINCREMENT,
            server_event_id INTEGER,
            player_id TEXT NOT NULL,
            qr_id TEXT NOT NULL,
            scenario_id TEXT NOT NULL,
            act_id TEXT NOT NULL,
            result TEXT NOT NULL,
            outcome TEXT NOT NULL,
            roll_log_json TEXT NOT NULL DEFAULT '[]',
            reward_id TEXT,
            reward_status TEXT NOT NULL,
            cooldown_until TEXT,
            payload_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            FOREIGN KEY (server_event_id) REFERENCES events(server_event_id)
        );

        CREATE INDEX IF NOT EXISTS idx_pve_attempts_player_qr
        ON pve_attempts(player_id, qr_id, created_at);

        CREATE TABLE IF NOT EXISTS pve_cooldowns (
            player_id TEXT NOT NULL,
            qr_id TEXT NOT NULL,
            cooldown_until TEXT NOT NULL,
            reason TEXT NOT NULL,
            source_event_id INTEGER,
            created_at TEXT NOT NULL,
            PRIMARY KEY (player_id, qr_id),
            FOREIGN KEY (source_event_id) REFERENCES events(server_event_id)
        );

        CREATE TABLE IF NOT EXISTS pve_consumed_objects (
            qr_id TEXT PRIMARY KEY,
            scenario_id TEXT NOT NULL,
            act_id TEXT NOT NULL,
            player_id TEXT NOT NULL,
            source_event_id INTEGER,
            consumed_at TEXT NOT NULL,
            payload_json TEXT NOT NULL DEFAULT '{}',
            FOREIGN KEY (source_event_id) REFERENCES events(server_event_id)
        );

        CREATE TABLE IF NOT EXISTS domain_runtime_state (
            domain_id TEXT PRIMARY KEY,
            lord_player_id TEXT,
            gold INTEGER NOT NULL DEFAULT 0,
            base_income INTEGER NOT NULL DEFAULT 0,
            current_mp INTEGER NOT NULL DEFAULT 0,
            mp_cap INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS territory_runtime_state (
            territory_id TEXT PRIMARY KEY,
            owner_domain_id TEXT,
            status TEXT NOT NULL DEFAULT 'neutral',
            contested_by_domain_id TEXT,
            controlled_since TEXT,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS territory_claim_runtime (
            claim_id TEXT PRIMARY KEY,
            territory_id TEXT NOT NULL,
            claimant_domain_id TEXT NOT NULL,
            defender_domain_id TEXT,
            status TEXT NOT NULL,
            source TEXT NOT NULL,
            created_at TEXT NOT NULL,
            resolved_at TEXT,
            battle_required INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS pending_tick_reward_runtime (
            pending_reward_id TEXT PRIMARY KEY,
            domain_id TEXT,
            territory_id TEXT NOT NULL,
            reward_gold INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'pending',
            due_at TEXT NOT NULL,
            awarded_to_domain_id TEXT,
            awarded_at TEXT
        );

        CREATE TABLE IF NOT EXISTS garrison_runtime_state (
            garrison_id TEXT PRIMARY KEY,
            territory_id TEXT NOT NULL,
            domain_id TEXT NOT NULL,
            card_id TEXT NOT NULL,
            count INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'active',
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS domain_buildings (
            domain_id TEXT NOT NULL,
            building_id TEXT NOT NULL,
            purchased_at TEXT NOT NULL,
            source TEXT NOT NULL,
            PRIMARY KEY (domain_id, building_id)
        );

        CREATE TABLE IF NOT EXISTS recruit_offer_runtime (
            offer_id TEXT PRIMARY KEY,
            domain_id TEXT NOT NULL,
            card_id TEXT NOT NULL,
            cost INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'available',
            source TEXT NOT NULL,
            held_by_domain_id TEXT,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS army_reserve_runtime (
            reserve_id TEXT PRIMARY KEY,
            domain_id TEXT NOT NULL,
            card_id TEXT NOT NULL,
            count INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'available',
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS active_army_runtime (
            army_id TEXT PRIMARY KEY,
            domain_id TEXT NOT NULL,
            card_id TEXT NOT NULL,
            count INTEGER NOT NULL DEFAULT 0,
            location_node_id TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS lord_battles (
            battle_id TEXT PRIMARY KEY,
            battle_type TEXT NOT NULL,
            territory_id TEXT,
            claim_id TEXT,
            attacker_domain_id TEXT NOT NULL,
            defender_domain_id TEXT,
            defender_control TEXT NOT NULL DEFAULT 'lord',
            status TEXT NOT NULL,
            seed TEXT NOT NULL,
            round_number INTEGER NOT NULL DEFAULT 1,
            active_side TEXT,
            active_stack_id TEXT,
            turn_started_at TEXT,
            timeout_at TEXT,
            timeout_counts_json TEXT NOT NULL DEFAULT '{}',
            board_json TEXT NOT NULL DEFAULT '{}',
            hero_hp_json TEXT NOT NULL DEFAULT '{}',
            deployment_json TEXT NOT NULL DEFAULT '{}',
            initiative_json TEXT NOT NULL DEFAULT '[]',
            burned_cards_json TEXT NOT NULL DEFAULT '[]',
            result_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            finished_at TEXT,
            target_duration_seconds INTEGER NOT NULL DEFAULT 1200,
            auto_resolve_after_seconds INTEGER NOT NULL DEFAULT 1500,
            master_takeover_enabled INTEGER NOT NULL DEFAULT 0
        );

        CREATE INDEX IF NOT EXISTS idx_lord_battles_domains
        ON lord_battles(attacker_domain_id, defender_domain_id, status);

        CREATE INDEX IF NOT EXISTS idx_lord_battles_claim
        ON lord_battles(claim_id, territory_id, status);

        CREATE TABLE IF NOT EXISTS lord_battle_actions (
            action_id TEXT NOT NULL,
            battle_id TEXT NOT NULL,
            actor_side TEXT NOT NULL,
            action_type TEXT NOT NULL,
            payload_json TEXT NOT NULL DEFAULT '{}',
            result_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            PRIMARY KEY (battle_id, action_id),
            FOREIGN KEY (battle_id) REFERENCES lord_battles(battle_id)
        );

        CREATE TABLE IF NOT EXISTS lord_battle_log (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            battle_id TEXT NOT NULL,
            round_number INTEGER NOT NULL DEFAULT 1,
            actor_side TEXT,
            entry_type TEXT NOT NULL,
            payload_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            FOREIGN KEY (battle_id) REFERENCES lord_battles(battle_id)
        );

        CREATE TABLE IF NOT EXISTS order_runtime_state (
            order_id TEXT PRIMARY KEY,
            lord_id TEXT NOT NULL,
            target_player_id TEXT,
            object_id TEXT NOT NULL,
            visibility TEXT NOT NULL,
            status TEXT NOT NULL,
            escrow_reward_id TEXT,
            accepted_by_player_id TEXT,
            submitted_by_player_id TEXT,
            result_event_id TEXT,
            reason TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS escrow_ledger (
            ledger_id TEXT PRIMARY KEY,
            order_id TEXT NOT NULL,
            reward_id TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            released_at TEXT,
            reason TEXT
        );

        CREATE TABLE IF NOT EXISTS army_windows (
            act_id TEXT NOT NULL,
            domain_id TEXT NOT NULL,
            status TEXT NOT NULL,
            opened_at TEXT NOT NULL,
            closes_at TEXT,
            payload_json TEXT NOT NULL DEFAULT '{}',
            PRIMARY KEY (act_id, domain_id)
        );

        CREATE TABLE IF NOT EXISTS applied_timer_ticks (
            timer_id TEXT NOT NULL,
            due_at TEXT NOT NULL,
            act_id TEXT NOT NULL,
            effect_type TEXT NOT NULL,
            applied_at TEXT NOT NULL,
            source TEXT NOT NULL,
            payload_json TEXT NOT NULL DEFAULT '{}',
            PRIMARY KEY (timer_id, due_at)
        );

        CREATE TABLE IF NOT EXISTS backup_runs (
            backup_id TEXT PRIMARY KEY,
            job_id TEXT NOT NULL,
            trigger_type TEXT NOT NULL,
            status TEXT NOT NULL,
            needs_master_review INTEGER NOT NULL DEFAULT 0,
            artifact_path TEXT,
            include_sqlite INTEGER NOT NULL DEFAULT 1,
            include_event_log INTEGER NOT NULL DEFAULT 1,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            operator TEXT NOT NULL,
            source TEXT NOT NULL,
            error TEXT
        );

        CREATE TABLE IF NOT EXISTS final_lock_state (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            locked_at TEXT,
            operator TEXT,
            source TEXT
        );

        INSERT INTO final_lock_state (id)
        VALUES (1)
        ON CONFLICT(id) DO NOTHING;

        CREATE TABLE IF NOT EXISTS pvp_throttle_state (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            mode TEXT NOT NULL DEFAULT 'normal',
            max_tables INTEGER NOT NULL DEFAULT 2,
            max_started_per_player_per_act INTEGER NOT NULL DEFAULT 2,
            final_lock_behavior TEXT NOT NULL DEFAULT 'no_new_challenges_after_final_lock',
            updated_at TEXT NOT NULL
        );

        INSERT INTO pvp_throttle_state (
            id, mode, max_tables, max_started_per_player_per_act,
            final_lock_behavior, updated_at
        )
        VALUES (
            1, 'normal', 2, 2, 'no_new_challenges_after_final_lock',
            CURRENT_TIMESTAMP
        )
        ON CONFLICT(id) DO NOTHING;

        CREATE TABLE IF NOT EXISTS pvp_table_runtime (
            table_id TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            zone_name TEXT NOT NULL,
            current_challenge_id TEXT,
            current_match_id TEXT,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS pvp_challenges (
            challenge_id TEXT PRIMARY KEY,
            challenger_id TEXT NOT NULL,
            target_id TEXT NOT NULL,
            act_id TEXT NOT NULL,
            status TEXT NOT NULL,
            mandatory INTEGER NOT NULL DEFAULT 1,
            stake_json TEXT NOT NULL DEFAULT '{}',
            table_id TEXT,
            assigned_zone TEXT,
            start_window_deadline TEXT,
            refusal_reason TEXT,
            review_reason TEXT,
            master_approval INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            started_at TEXT,
            resolved_at TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_pvp_challenges_players
        ON pvp_challenges(challenger_id, target_id, status);

        CREATE TABLE IF NOT EXISTS gwent_runtime_matches (
            match_id TEXT PRIMARY KEY,
            challenge_id TEXT NOT NULL UNIQUE,
            challenger_id TEXT NOT NULL,
            target_id TEXT NOT NULL,
            act_id TEXT NOT NULL,
            status TEXT NOT NULL,
            table_id TEXT,
            deck_state_json TEXT NOT NULL DEFAULT '{}',
            round_losses_json TEXT NOT NULL DEFAULT '{}',
            winner_id TEXT,
            review_reason TEXT,
            created_at TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            result_applied_at TEXT,
            duration_seconds INTEGER,
            balance_report_json TEXT NOT NULL DEFAULT '{}',
            FOREIGN KEY (challenge_id) REFERENCES pvp_challenges(challenge_id)
        );

        CREATE TABLE IF NOT EXISTS gwent_rounds (
            round_id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id TEXT NOT NULL,
            round_number INTEGER NOT NULL,
            round_state_json TEXT NOT NULL DEFAULT '{}',
            row_scores_json TEXT NOT NULL DEFAULT '{}',
            passed_json TEXT NOT NULL DEFAULT '{}',
            winner_id TEXT,
            tie INTEGER NOT NULL DEFAULT 0,
            review_required INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            UNIQUE(match_id, round_number),
            FOREIGN KEY (match_id) REFERENCES gwent_runtime_matches(match_id)
        );

        CREATE TABLE IF NOT EXISTS pvp_stake_ledger (
            stake_ledger_id TEXT PRIMARY KEY,
            challenge_id TEXT NOT NULL,
            match_id TEXT,
            asset_type TEXT NOT NULL,
            asset_id TEXT NOT NULL,
            owner_player_id TEXT NOT NULL,
            pending_target_player_id TEXT NOT NULL,
            status TEXT NOT NULL,
            winner_id TEXT,
            loser_id TEXT,
            created_at TEXT NOT NULL,
            applied_at TEXT
        );

        CREATE TABLE IF NOT EXISTS pvp_reviews (
            review_id INTEGER PRIMARY KEY AUTOINCREMENT,
            challenge_id TEXT,
            match_id TEXT,
            reason TEXT NOT NULL,
            severity TEXT NOT NULL DEFAULT 'P2',
            status TEXT NOT NULL DEFAULT 'needs_master_review',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS personal_card_conversions (
            conversion_id TEXT PRIMARY KEY,
            player_id TEXT NOT NULL,
            lord_id TEXT NOT NULL,
            domain_id TEXT,
            personal_card_id TEXT NOT NULL,
            army_unit_card_id TEXT NOT NULL,
            tier INTEGER NOT NULL,
            status TEXT NOT NULL,
            source TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(player_id, personal_card_id)
        );

        CREATE TABLE IF NOT EXISTS potion_market_runtime (
            market_id TEXT PRIMARY KEY,
            seller_role TEXT NOT NULL,
            potion_id TEXT NOT NULL,
            stock INTEGER NOT NULL DEFAULT 0,
            refresh_rule TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS potion_inventory (
            inventory_id TEXT PRIMARY KEY,
            player_id TEXT NOT NULL,
            potion_id TEXT NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL,
            UNIQUE(player_id, potion_id)
        );

        CREATE TABLE IF NOT EXISTS potion_scene_usage (
            usage_id TEXT PRIMARY KEY,
            player_id TEXT NOT NULL,
            potion_id TEXT NOT NULL,
            scene_id TEXT NOT NULL,
            source TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(player_id, scene_id)
        );

        CREATE TABLE IF NOT EXISTS trade_transfer_runtime (
            transfer_id TEXT PRIMARY KEY,
            from_player_id TEXT NOT NULL,
            to_player_id TEXT NOT NULL,
            asset_type TEXT NOT NULL,
            asset_id TEXT NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 1,
            price_gold INTEGER NOT NULL DEFAULT 0,
            mode TEXT NOT NULL,
            status TEXT NOT NULL,
            accepted_at TEXT,
            source TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_trade_transfer_runtime_asset
        ON trade_transfer_runtime(asset_type, asset_id, status);

        CREATE TABLE IF NOT EXISTS sorceress_spell_casts (
            cast_id TEXT PRIMARY KEY,
            sorceress_id TEXT NOT NULL,
            spell_id TEXT NOT NULL,
            target_type TEXT NOT NULL,
            target_id TEXT NOT NULL,
            cost_mana INTEGER NOT NULL DEFAULT 0,
            effect_json TEXT NOT NULL DEFAULT '{}',
            counterplay TEXT NOT NULL DEFAULT '',
            visibility TEXT NOT NULL,
            status TEXT NOT NULL,
            review_reason TEXT,
            source TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS magic_effects (
            effect_id TEXT PRIMARY KEY,
            cast_id TEXT NOT NULL,
            sorceress_id TEXT NOT NULL,
            spell_id TEXT NOT NULL,
            target_type TEXT NOT NULL,
            target_id TEXT NOT NULL,
            effect_json TEXT NOT NULL DEFAULT '{}',
            counterplay TEXT NOT NULL DEFAULT '',
            visibility TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (cast_id) REFERENCES sorceress_spell_casts(cast_id)
        );

        CREATE TABLE IF NOT EXISTS locked_magical_intent (
            intent_id TEXT PRIMARY KEY,
            sorceress_id TEXT NOT NULL,
            cast_id TEXT,
            target_id TEXT NOT NULL,
            intent_json TEXT NOT NULL DEFAULT '{}',
            status TEXT NOT NULL,
            review_reason TEXT,
            locked_at TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS favorite_runtime (
            favorite_id TEXT PRIMARY KEY,
            sorceress_id TEXT NOT NULL,
            favored_player_id TEXT NOT NULL,
            slot TEXT NOT NULL,
            status TEXT NOT NULL,
            changed_in_act TEXT NOT NULL,
            consent_required INTEGER NOT NULL DEFAULT 1,
            passive_bonus_allowed INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            accepted_at TEXT,
            ended_at TEXT,
            source TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_favorite_runtime_favored
        ON favorite_runtime(favored_player_id, status);

        CREATE TABLE IF NOT EXISTS favorite_history (
            history_id TEXT PRIMARY KEY,
            favorite_id TEXT NOT NULL,
            sorceress_id TEXT NOT NULL,
            favored_player_id TEXT NOT NULL,
            slot TEXT NOT NULL,
            act_id TEXT NOT NULL,
            action TEXT NOT NULL,
            passive_bonus_allowed INTEGER NOT NULL DEFAULT 0,
            source TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS sorceress_alignment_evidence (
            evidence_id TEXT PRIMARY KEY,
            sorceress_id TEXT NOT NULL,
            alignment_state TEXT NOT NULL,
            evidence_type TEXT NOT NULL,
            payload_json TEXT NOT NULL DEFAULT '{}',
            visibility TEXT NOT NULL,
            final_flag INTEGER NOT NULL DEFAULT 0,
            source TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS final_master_notes (
            note_id TEXT PRIMARY KEY,
            category TEXT NOT NULL,
            target_id TEXT,
            note_text TEXT NOT NULL,
            visibility TEXT NOT NULL DEFAULT 'masters',
            operator TEXT NOT NULL,
            source TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """
    )
    _ensure_columns(
        connection,
        "player_runtime_state",
        {
            "xp": "INTEGER NOT NULL DEFAULT 0",
            "stats_json": "TEXT NOT NULL DEFAULT '{}'",
        },
    )
    _ensure_columns(
        connection,
        "domain_runtime_state",
        {
            "current_node_id": "TEXT",
            "active_army_capacity": "INTEGER NOT NULL DEFAULT 4",
            "raid_tokens": "INTEGER NOT NULL DEFAULT 1",
            "influence": "INTEGER NOT NULL DEFAULT 0",
        },
    )
    _ensure_columns(
        connection,
        "escrow_ledger",
        {
            "reserved_gold": "INTEGER NOT NULL DEFAULT 0",
            "reserved_xp": "INTEGER NOT NULL DEFAULT 0",
            "reserved_assets_json": "TEXT NOT NULL DEFAULT '[]'",
            "reserved_from_domain_id": "TEXT",
            "awarded_to_player_id": "TEXT",
        },
    )


def _ensure_columns(
    connection: sqlite3.Connection,
    table_name: str,
    columns: dict[str, str],
) -> None:
    existing = {
        row["name"]
        for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    }
    for column_name, definition in columns.items():
        if column_name not in existing:
            connection.execute(
                f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}"
            )


def log_event(
    connection: sqlite3.Connection,
    event_type: str,
    payload: dict[str, Any],
    *,
    source: str,
    created_at: datetime | None = None,
) -> int:
    timestamp = (created_at or datetime.now(UTC)).isoformat(timespec="seconds")
    payload_with_timestamp = dict(payload)
    payload_with_timestamp.setdefault("server_timestamp", timestamp)
    cursor = connection.execute(
        """
        INSERT INTO event_log (event_type, payload_json, source, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (
            event_type,
            json.dumps(payload_with_timestamp, ensure_ascii=False, sort_keys=True),
            source,
            timestamp,
        ),
    )
    return int(cursor.lastrowid)
