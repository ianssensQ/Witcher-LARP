"""Runtime CSV table names and small schema helpers."""

from __future__ import annotations


TABLE_ID_COLUMNS: dict[str, str] = {
    "act_unlock_codes.csv": "unlock_id",
    "acts.csv": "act_id",
    "anti_snowball_rules.csv": "rule_id",
    "army_reserves.csv": "reserve_id",
    "army_unit_cards.csv": "card_id",
    "artifacts.csv": "artifact_id",
    "auto_timers.csv": "timer_id",
    "backup_jobs.csv": "job_id",
    "balance_defaults.csv": "rule_id",
    "buildings.csv": "building_id",
    "cards.csv": "card_id",
    "challenge_tokens.csv": "token_rule_id",
    "check_policies.csv": "policy_id",
    "diplomacy_signals.csv": "signal_id",
    "domains.csv": "domain_id",
    "favorite_rules.csv": "rule_id",
    "favorites.csv": "favorite_id",
    "final_hooks.csv": "final_hook_id",
    "final_procedures.csv": "procedure_id",
    "final_summary.csv": "summary_id",
    "final_summary_fields.csv": "field_id",
    "garrisons.csv": "garrison_id",
    "goal_flags.csv": "flag_id",
    "goal_tracks.csv": "track_id",
    "gwent_cards.csv": "card_id",
    "gwent_decks.csv": "deck_id",
    "gwent_matches.csv": "match_id",
    "gwent_rules.csv": "rule_id",
    "items.csv": "item_id",
    "lord_battle_rules.csv": "rule_id",
    "map_edges.csv": "edge_id",
    "map_nodes.csv": "node_id",
    "mobs.csv": "mob_id",
    "movement_pools.csv": "pool_id",
    "movement_rules.csv": "rule_id",
    "npc_events.csv": "event_id",
    "ops_checklists.csv": "item_id",
    "order_status_rules.csv": "status_id",
    "orders.csv": "order_id",
    "paper_forms.csv": "form_type",
    "pending_tick_rewards.csv": "pending_reward_id",
    "personal_goals.csv": "goal_id",
    "physical_announcements.csv": "announcement_id",
    "player_codes.csv": "code_id",
    "player_handouts.csv": "handout_id",
    "players.csv": "player_id",
    "potion_markets.csv": "market_id",
    "potions.csv": "potion_id",
    "profiles.csv": "profile_id",
    "pve_combat_rules.csv": "rule_id",
    "pve_scenarios.csv": "scenario_id",
    "pvp_refusal_rules.csv": "rule_id",
    "pvp_tables.csv": "table_id",
    "pvp_throttle_rules.csv": "rule_id",
    "qr_objects.csv": "qr_id",
    "qr_policies.csv": "policy_id",
    "raid_rules.csv": "rule_id",
    "rarity_rules.csv": "rule_id",
    "recruit_markets.csv": "offer_id",
    "reputation_rules.csv": "rule_id",
    "review_severity_rules.csv": "severity",
    "reward_approval_rules.csv": "rule_id",
    "rewards.csv": "reward_id",
    "role_tokens.csv": "token_id",
    "sorceress_alignment_rules.csv": "rule_id",
    "spells.csv": "spell_id",
    "territories.csv": "territory_id",
    "territory_forts.csv": "fort_id",
    "territory_claims.csv": "claim_id",
    "trade_transfers.csv": "transfer_id",
    "venue_map_profiles.csv": "profile_id",
    "xp_rules.csv": "rule_id",
}

REQUIRED_FILES: tuple[str, ...] = tuple(sorted(TABLE_ID_COLUMNS))


def table_name(file_name: str) -> str:
    if not file_name.endswith(".csv"):
        raise ValueError(f"CSV file name must end with .csv: {file_name}")
    return file_name[:-4]


def split_ids(value: str) -> list[str]:
    return [part.strip() for part in value.split(";") if part.strip()]
