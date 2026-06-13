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
    "commanders_horn",
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
}

GWENT_LEADER_EFFECTS = {
    "leader_foltest_fog",
    "leader_foltest_clear_weather",
    "leader_foltest_siege_horn",
    "leader_foltest_siege_scorch",
    "leader_emhyr_spy_hand",
    "leader_emhyr_rain",
    "leader_emhyr_graveyard_theft",
    "leader_emhyr_cancel_leader",
    "leader_francesca_draw",
    "leader_francesca_frost",
    "leader_francesca_melee_scorch",
    "leader_francesca_ranged_horn",
    "leader_eredin_graveyard_return",
    "leader_eredin_melee_horn",
    "leader_eredin_discard_draw",
    "leader_eredin_weather",
    "leader_crach_graveyard_shuffle",
}

GWENT_SUPPORTED_EFFECTS_BY_TYPE = {
    "unit": GWENT_UNIT_EFFECTS,
    "special": GWENT_SPECIAL_EFFECTS,
    "leader": GWENT_LEADER_EFFECTS,
}


def is_gwent_effect_supported(card_type: str, effect: str) -> bool:
    return effect in GWENT_SUPPORTED_EFFECTS_BY_TYPE.get(card_type, set())
