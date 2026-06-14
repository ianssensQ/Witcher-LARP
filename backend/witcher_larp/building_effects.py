"""Canonical gameplay effects for lord residence buildings."""

from __future__ import annotations

from collections.abc import Iterable


PUBLIC_ORDER_BUILDING_ID = "b_notice_board"
ADDRESSED_ORDER_BUILDING_ID = "b_envoy_hall"
STOREHOUSE_BUILDING_ID = "b_storehouse"
BANK_BUILDING_ID = "b_bank"
TAX_OFFICE_BUILDING_ID = "b_tax_office"
TREASURY_HALL_BUILDING_ID = "b_treasury_hall"
MAGE_STUDY_BUILDING_ID = "b_mage_study"
ALCHEMY_LAB_BUILDING_ID = "b_alchemy_lab"
RITUAL_CHAMBER_BUILDING_ID = "b_ritual_chamber"

PUBLIC_ORDER_LIMIT_WITH_BUILDING = 2
ADDRESSED_ORDER_LIMIT_WITH_BUILDING = 1
STOREHOUSE_STOCK_CAP_PERCENT = 200
TAX_OFFICE_TERRITORY_INCOME_BONUS_PERCENT = 50
TREASURY_INCOME_FLOOR_PERCENT = 50
BANK_LOOT_REDUCTION_PERCENT = 50
MAGE_STUDY_RESIDENCE_DEFENSE_BONUS = 1
ALCHEMY_RAID_DURATION_REDUCTION_MINUTES = 15
RITUAL_CLEANSE_CHARGE_CAP = 1

FLAT_INCOME_BY_BUILDING_ID = {
    "b_market": 8,
    BANK_BUILDING_ID: 15,
    TREASURY_HALL_BUILDING_ID: 25,
}

BUILDING_EFFECT_LABELS = {
    "b_training_yard": [
        "Максимум активной армии +1",
        "Открывает найм мечников",
    ],
    "b_barracks": ["Открывает найм стражи"],
    "b_archery_range": ["Открывает найм лучников"],
    "b_stables": [
        "Максимум активной армии +1",
        "Открывает найм кавалерии",
    ],
    "b_siege_yard": ["Открывает найм осадников"],
    "b_war_academy": [
        "Максимум активной армии +1",
        "Открывает найм инженеров",
        "Кап рейдовых жетонов +2",
    ],
    "b_market": ["Доход за тик +8 золота"],
    "b_tax_office": ["Доход с контролируемых территорий +50%"],
    "b_storehouse": ["Лимит накопления открытых войск: 4 тика вместо 2"],
    BANK_BUILDING_ID: [
        "Доход за тик +15 золота",
        "Налет за добычей крадет на 50% меньше золота",
    ],
    TREASURY_HALL_BUILDING_ID: [
        "Доход за тик +25 золота",
        "Итоговый доход не падает ниже 50% от дохода до штрафов",
    ],
    PUBLIC_ORDER_BUILDING_ID: [
        "Открывает публичные заказы",
        "Лимит публичных заказов: 2 активных",
    ],
    ADDRESSED_ORDER_BUILDING_ID: [
        "Открывает адресные заказы",
        "Лимит адресных заказов: 1 активный",
    ],
    "b_map_room": [
        "Открывает список целей рейда",
        "Показывает общий риск защиты цели",
    ],
    "b_raid_office": [
        "Кап рейдовых жетонов +2",
        "Открывает территориальные рейды",
    ],
    "b_war_council": [
        "Максимум активной армии +1",
        "Кап рейдовых жетонов +1",
        "Открывает рейд Черная печать",
        "С Комнатой видений открывает рейд по резиденции",
    ],
    MAGE_STUDY_BUILDING_ID: ["Защита резиденции от рейдов +1"],
    ALCHEMY_LAB_BUILDING_ID: [
        "Длительность входящих рейд-эффектов -15 минут",
        "Мгновенный лут-рейд не сокращается",
    ],
    "b_scrying_room": [
        "Показывает точную защиту цели",
        "Показывает силу гарнизона цели",
        "Показывает обереги и активную армию цели",
    ],
    "b_wards": [
        "Обычные территории: защита от рейдов +1",
        "Резиденция: защита от рейдов +2",
    ],
    RITUAL_CHAMBER_BUILDING_ID: [
        "Раз в доходный тик дает 1 заряд очищения",
        "Заряд снимает один активный рейд-эффект с владений дома",
    ],
}


def building_effect_labels(building_id: str) -> list[str]:
    return list(BUILDING_EFFECT_LABELS.get(building_id, ["Бонус владения"]))


def owned_building_ids(rows: Iterable[object]) -> set[str]:
    ids: set[str] = set()
    for row in rows:
        if isinstance(row, dict):
            building_id = row.get("building_id")
        else:
            building_id = getattr(row, "building_id", None)
        if building_id:
            ids.add(str(building_id))
    return ids


def flat_income_bonus(building_ids: Iterable[str]) -> int:
    return sum(FLAT_INCOME_BY_BUILDING_ID.get(building_id, 0) for building_id in building_ids)


def territory_income_bonus_percent(building_ids: Iterable[str]) -> int:
    return TAX_OFFICE_TERRITORY_INCOME_BONUS_PERCENT if TAX_OFFICE_BUILDING_ID in set(building_ids) else 0


def stock_cap_percent(building_ids: Iterable[str]) -> int:
    return STOREHOUSE_STOCK_CAP_PERCENT if STOREHOUSE_BUILDING_ID in set(building_ids) else 100


def treasury_income_floor_percent(building_ids: Iterable[str]) -> int:
    return TREASURY_INCOME_FLOOR_PERCENT if TREASURY_HALL_BUILDING_ID in set(building_ids) else 0
