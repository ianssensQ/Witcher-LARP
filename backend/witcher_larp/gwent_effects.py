"""Supported Stage 1 Gwent effects shared by runtime and seed validation."""

from __future__ import annotations

GWENT_ROWS = ("melee", "ranged", "siege")

GWENT_WEATHER_BY_EFFECT = {
    "weather_melee": "melee",
    "biting_frost": "melee",
    "weather_ranged": "ranged",
    "impenetrable_fog": "ranged",
    "weather_siege": "siege",
    "torrential_rain": "siege",
}

GWENT_UNIT_EFFECTS = {
    "none",
    "morale",
    "bond",
    "tight_bond",
    "agile",
    "hero",
    "spy",
    "medic",
    "muster",
    "scorch_melee",
    "scorch_ranged",
    "scorch_siege",
}

GWENT_SPECIAL_EFFECTS = {
    *GWENT_WEATHER_BY_EFFECT,
    "clear_weather",
    "commanders_horn",
    "decoy",
    "scorch",
    "custom_larp_order_banner",
    "custom_larp_spyglass",
    "custom_larp_oathbreak",
    "custom_larp_last_stand",
}

GWENT_LEADER_EFFECTS = {"leader_order_rally"}

GWENT_SUPPORTED_EFFECTS_BY_TYPE = {
    "unit": GWENT_UNIT_EFFECTS,
    "special": GWENT_SPECIAL_EFFECTS,
    "leader": GWENT_LEADER_EFFECTS,
}


def is_gwent_effect_supported(card_type: str, effect: str) -> bool:
    return effect in GWENT_SUPPORTED_EFFECTS_BY_TYPE.get(card_type, set())
