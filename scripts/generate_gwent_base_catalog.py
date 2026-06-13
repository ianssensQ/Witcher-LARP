"""Generate the first-iteration Witcher 3 base Gwent card seed.

The source list intentionally covers the four base-game factions plus neutral
base cards. Skellige, Hearts of Stone, Blood and Wine, and post-release reward
cards stay out of this first iteration.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SEED_DIR = ROOT / "data" / "seed"
CHECKLIST_PATH = ROOT / "docs" / "gwent-card-checklist.md"

CARD_FIELDS = [
    "card_id",
    "faction",
    "row",
    "type",
    "strength",
    "effect",
    "rarity",
    "ability_tags",
    "name_group",
    "bond_group",
    "muster_group",
    "display_name",
    "effect_text",
    "deck_limit",
    "source_set",
]


@dataclass(frozen=True)
class Card:
    card_id: str
    faction: str
    row: str
    type: str
    strength: int
    effect: str
    rarity: str
    ability_tags: str
    name_group: str
    bond_group: str
    muster_group: str
    display_name: str
    effect_text: str
    deck_limit: int = 1
    source_set: str = "witcher3_base"

    def row_dict(self) -> dict[str, object]:
        return {field: getattr(self, field) for field in CARD_FIELDS}


EFFECT_TEXT = {
    "none": "Без особого эффекта.",
    "hero": "Герой: не подвержен погоде, казни, рогу и большинству способностей.",
    "spy": "Шпион: кладется на сторону соперника и дает вам добор двух карт.",
    "medic": "Лекарь: выбирает обычную карту из вашего сброса и сразу играет ее.",
    "muster": "Сбор: вытаскивает из руки и колоды все карты той же группы.",
    "morale": "Боевой дух: дает +1 всем другим обычным картам в этом ряду.",
    "tight_bond": "Связка: карты одной группы умножают свою силу друг на друга.",
    "agile": "Гибкая карта: может быть сыграна в ближний или дальний ряд.",
    "weather_melee": "Мороз: сила всех обычных карт ближнего ряда у обоих игроков становится 1.",
    "weather_ranged": "Туман: сила всех обычных карт дальнего ряда у обоих игроков становится 1.",
    "weather_siege": "Ливень: сила всех обычных карт осадного ряда у обоих игроков становится 1.",
    "clear_weather": "Ясная погода: убирает все погодные эффекты со стола.",
    "commanders_horn": "Командирский рог: удваивает силу обычных карт выбранного вашего ряда.",
    "decoy": "Чучело: возвращает вашу обычную карту со стола в руку и уходит в сброс.",
    "scorch": "Казнь: уничтожает самые сильные обычные карты на столе.",
    "scorch_melee": "Казнь ближнего ряда: уничтожает сильнейшие обычные карты ближнего ряда соперника при сумме ряда 10+.",
    "scorch_ranged": "Казнь дальнего ряда: уничтожает сильнейшие обычные карты дальнего ряда соперника при сумме ряда 10+.",
    "scorch_siege": "Казнь осадного ряда: уничтожает сильнейшие обычные карты осадного ряда соперника при сумме ряда 10+.",
    "leader_foltest_fog": "Лидер: достает из колоды Непроницаемый туман и сразу применяет его.",
    "leader_foltest_clear_weather": "Лидер: убирает все погодные эффекты со стола.",
    "leader_foltest_siege_horn": "Лидер: удваивает силу вашего осадного ряда как командирский рог.",
    "leader_foltest_siege_scorch": "Лидер: казнит сильнейшие обычные карты осадного ряда соперника при сумме ряда 10+.",
    "leader_emhyr_spy_hand": "Лидер: смотрит три случайные карты в руке соперника.",
    "leader_emhyr_rain": "Лидер: достает из колоды Ливень и сразу применяет его.",
    "leader_emhyr_graveyard_theft": "Лидер: берет одну обычную карту из сброса соперника в вашу руку.",
    "leader_emhyr_cancel_leader": "Лидер: запрещает сопернику использовать способность его лидера.",
    "leader_francesca_draw": "Лидер: дает одну дополнительную карту в начале партии.",
    "leader_francesca_frost": "Лидер: достает из колоды Мороз и сразу применяет его.",
    "leader_francesca_melee_scorch": "Лидер: казнит сильнейшие обычные карты ближнего ряда соперника при сумме ряда 10+.",
    "leader_francesca_ranged_horn": "Лидер: удваивает силу вашего дальнего ряда как командирский рог.",
    "leader_eredin_graveyard_return": "Лидер: возвращает одну обычную карту из вашего сброса в руку.",
    "leader_eredin_melee_horn": "Лидер: удваивает силу вашего ближнего ряда как командирский рог.",
    "leader_eredin_discard_draw": "Лидер: сбрасывает две карты из руки и добирает одну карту из колоды.",
    "leader_eredin_weather": "Лидер: достает из колоды первую погодную карту и сразу применяет ее.",
}

RU_DISPLAY_NAMES = {
    "Albrich": "Альбрых",
    "Arachas": "Арахас",
    "Arachas Behemoth": "Арахас-бегемот",
    "Assire var Anahid": "Ассирэ вар Анагыд",
    "Ballista": "Баллиста",
    "Barclay Els": "Барклай Эльс",
    "Biting Frost": "Мороз",
    "Black Infantry Archer": "Лучник Черной пехоты",
    "Blue Stripes Commando": "Боец Синих Полос",
    "Botchling": "Игоша",
    "Cahir Mawr Dyffryn aep Ceallach": "Кагыр Маур Дыффин аэп Кеаллах",
    "Catapult": "Катапульта",
    "Celaeno Harpy": "Гарпия келено",
    "Ciaran aep Easnillien": "Киаран аэп Эасниллен",
    "Cirilla Fiona Elen Riannon": "Цирилла Фиона Элен Рианнон",
    "Clear Weather": "Ясная погода",
    "Cockatrice": "Кокатрикс",
    "Commander's Horn": "Командирский рог",
    "Crinfrid Reavers Dragon Hunter": "Охотник на драконов из Кринфрида",
    "Crone: Brewess": "Ведьма: Кухарка",
    "Crone: Weavess": "Ведьма: Пряха",
    "Crone: Whispess": "Ведьма: Шептуха",
    "Cynthia": "Цинтия",
    "Dandelion": "Лютик",
    "Decoy": "Чучело",
    "Dennis Cranmer": "Деннис Кранмер",
    "Dethmold": "Детмольд",
    "Dol Blathanna Archer": "Лучник Дол Блатанны",
    "Dol Blathanna Scout": "Разведчик Дол Блатанны",
    "Draug": "Драуг",
    "Dun Banner Medic": "Лекарь Бурой Хоругви",
    "Dwarven Skirmisher": "Краснолюд-застрельщик",
    "Earth Elemental": "Земной элементаль",
    "Eithne": "Эитнэ",
    "Elven Skirmisher": "Эльф-застрельщик",
    "Emhyr var Emreis: Emperor of Nilfgaard": "Эмгыр вар Эмрейс: Император Нильфгаарда",
    "Emhyr var Emreis: His Imperial Majesty": "Эмгыр вар Эмрейс: Его императорское величество",
    "Emhyr var Emreis: The Relentless": "Эмгыр вар Эмрейс: Неумолимый",
    "Emhyr var Emreis: The White Flame": "Эмгыр вар Эмрейс: Белое Пламя",
    "Emiel Regis Rohellec Terzieff": "Эмиель Регис Рогеллек Терзиефф",
    "Endrega": "Эндриага",
    "Eredin: Bringer of Death": "Эредин: Несущий смерть",
    "Eredin: Commander of the Red Riders": "Эредин: Командир Красных Всадников",
    "Eredin: Destroyer of Worlds": "Эредин: Разрушитель миров",
    "Eredin: King of the Wild Hunt": "Эредин: Король Дикой Охоты",
    "Esterad Thyssen": "Эстерад Тиссен",
    "Etolian Auxiliary Archers": "Этолийские вспомогательные лучники",
    "Fiend": "Бес",
    "Filavandrel aen Fidhail": "Филавандрель аэн Фидаиль",
    "Fire Elemental": "Огненный элементаль",
    "Foglet": "Туманник",
    "Foltest: King of Temeria": "Фольтест: Король Темерии",
    "Foltest: Lord Commander of the North": "Фольтест: Предводитель Севера",
    "Foltest: The Siegemaster": "Фольтест: Мастер осады",
    "Foltest: The Steel-Forged": "Фольтест: Закаленный сталью",
    "Forktail": "Вилохвост",
    "Francesca Findabair: Daisy of the Valley": "Францеска Финдабаир: Маргаритка из Долин",
    "Francesca Findabair: Pureblood Elf": "Францеска Финдабаир: Чистокровная эльфка",
    "Francesca Findabair: Queen of Dol Blathanna": "Францеска Финдабаир: Королева Дол Блатанны",
    "Francesca Findabair: The Beautiful": "Францеска Финдабаир: Прекрасная",
    "Frightener": "Пугач",
    "Fringilla Vigo": "Фрингилья Виго",
    "Gargoyle": "Гаргулья",
    "Geralt of Rivia": "Геральт из Ривии",
    "Ghoul": "Гуль",
    "Grave Hag": "Кладбищенская баба",
    "Griffin": "Грифон",
    "Harpy": "Гарпия",
    "Havekar Healer": "Гавенкар-лекарь",
    "Havekar Smuggler": "Гавенкар-контрабандист",
    "Heavy Zerrikanian Fire Scorpion": "Тяжелый зэрриканский огненный скорпион",
    "Ice Giant": "Ледяной великан",
    "Ida Emean aep Sivney": "Ида Эмеан аэп Сивней",
    "Imlerith": "Имлерих",
    "Impenetrable Fog": "Непроницаемый туман",
    "Impera Brigade Guard": "Гвардеец бригады Импера",
    "Iorveth": "Иорвет",
    "Isengrim Faoiltiarna": "Изенгрим Фаоильтиарна",
    "John Natalis": "Ян Наталис",
    "Kaedweni Siege Expert": "Каэдвенский осадный мастер",
    "Kayran": "Кейран",
    "Keira Metz": "Кейра Мец",
    "Leshen": "Леший",
    "Letho of Gulet": "Лето из Гулеты",
    "Mahakaman Defender": "Защитник Махакам",
    "Menno Coehoorn": "Менно Коегоорн",
    "Milva": "Мильва",
    "Morteisen": "Мортейзен",
    "Morvran Voorhis": "Морвран Воорхис",
    "Mysterious Elf": "Таинственный эльф",
    "Nausicaa Cavalry Rider": "Всадник кавалерии Наузикаа",
    "Nekker": "Накер",
    "Philippa Eilhart": "Филиппа Эйльхарт",
    "Plague Maiden": "Моровая дева",
    "Poor Fucking Infantry": "Проклятая пехота",
    "Prince Stennis": "Принц Стеннис",
    "Puttkammer": "Путткамер",
    "Rainfarn": "Райнфарн",
    "Redanian Foot Soldier": "Реданский пехотинец",
    "Renuald aep Matsen": "Ренуальд аэп Матсен",
    "Riordain": "Риордаин",
    "Rotten Mangonel": "Гнилая мангонель",
    "Sabrina Glevissig": "Сабрина Глевиссиг",
    "Saesenthessis": "Саэсентессис",
    "Scorch": "Казнь",
    "Sheldon Skaggs": "Шелдон Скаггс",
    "Shilard Fitz-Oesterlen": "Шилярд Фиц-Эстерлен",
    "Siege Engineer": "Осадный инженер",
    "Siege Technician": "Осадный техник",
    "Siege Tower": "Осадная башня",
    "Siegfried of Denesle": "Зигфрид из Денесле",
    "Sigismund Dijkstra": "Сигизмунд Дийкстра",
    "Sile de Tansarville": "Шеала де Тансервилль",
    "Stefan Skellen": "Стефан Скеллен",
    "Sweers": "Свирс",
    "Thaler": "Талер",
    "Tibor Eggebracht": "Тибор Эггебрахт",
    "Torrential Rain": "Ливень",
    "Toruviel": "Торувьель",
    "Trebuchet": "Требушет",
    "Triss Merigold": "Трисс Меригольд",
    "Vampire: Bruxa": "Вампир: Брукса",
    "Vampire: Ekimmara": "Вампир: Экимма",
    "Vampire: Fleder": "Вампир: Фледер",
    "Vampire: Garkain": "Вампир: Гаркаин",
    "Vampire: Katakan": "Вампир: Катакан",
    "Vanhemar": "Вангемар",
    "Vattier de Rideaux": "Ватье де Ридо",
    "Vernon Roche": "Вернон Роше",
    "Ves": "Вес",
    "Vesemir": "Весемир",
    "Villentretenmerth": "Виллентретенмерт",
    "Vreemde": "Вреемде",
    "Vrihedd Brigade Recruit": "Новобранец бригады Врихедд",
    "Vrihedd Brigade Veteran": "Ветеран бригады Врихедд",
    "Werewolf": "Вервольф",
    "Wyvern": "Виверна",
    "Yaevinn": "Яевинн",
    "Yarpen Zigrin": "Ярпен Зигрин",
    "Yennefer of Vengerberg": "Йеннифэр из Венгерберга",
    "Young Emissary": "Молодой посол",
    "Zerrikanian Fire Scorpion": "Зэрриканский огненный скорпион",
    "Zoltan Chivay": "Золтан Хивай",
}


cards: list[Card] = []


def localized_display_name(display_name: str) -> str:
    try:
        return RU_DISPLAY_NAMES[display_name]
    except KeyError as exc:
        raise ValueError(f"Missing Russian Gwent display name: {display_name}") from exc


def add(
    card_id: str,
    faction: str,
    row: str,
    card_type: str,
    strength: int,
    effect: str = "none",
    *,
    rarity: str = "Common",
    tags: str = "",
    name_group: str | None = None,
    bond_group: str = "",
    muster_group: str = "",
    display_name: str,
    effect_text: str | None = None,
) -> str:
    resolved_text = effect_text or "; ".join(
        EFFECT_TEXT[item] for item in [effect, *split_tags(tags)] if item and item != "none"
    ) or EFFECT_TEXT["none"]
    cards.append(
        Card(
            card_id=card_id,
            faction=faction,
            row=row,
            type=card_type,
            strength=strength,
            effect=effect,
            rarity=rarity,
            ability_tags=tags,
            name_group=name_group or card_id,
            bond_group=bond_group,
            muster_group=muster_group,
            display_name=localized_display_name(display_name),
            effect_text=resolved_text,
        )
    )
    return card_id


def split_tags(raw: str) -> list[str]:
    return [part.strip() for part in raw.split(";") if part.strip()]


def copies(
    base_id: str,
    count: int,
    faction: str,
    row: str,
    strength: int,
    effect: str,
    *,
    card_type: str = "unit",
    display_name: str,
    rarity: str = "Common",
    tags: str = "",
    name_group: str | None = None,
    bond_group: str = "",
    muster_group: str = "",
    first_id: str | None = None,
) -> list[str]:
    ids = []
    for index in range(1, count + 1):
        card_id = first_id if index == 1 and first_id else f"{base_id}_{index}"
        ids.append(
            add(
                card_id,
                faction,
                row,
                card_type,
                strength,
                effect,
                rarity=rarity,
                tags=tags,
                name_group=name_group or base_id,
                bond_group=bond_group,
                muster_group=muster_group,
                display_name=display_name,
            )
        )
    return ids


def special_copies(
    base_id: str,
    count: int,
    row: str,
    effect: str,
    *,
    display_name: str,
    first_id: str | None = None,
) -> list[str]:
    return copies(
        base_id,
        count,
        "neutral",
        row,
        0,
        effect,
        card_type="special",
        display_name=display_name,
        rarity="Special",
        first_id=first_id,
    )


def leader(card_id: str, faction: str, effect: str, display_name: str) -> str:
    return add(
        card_id,
        faction,
        "leader",
        "leader",
        0,
        effect,
        rarity="Leader",
        name_group=card_id,
        display_name=display_name,
    )


# Leaders: four base-game leaders for each of the four base factions.
leader("gwent_leader_foltest_king", "northern", "leader_foltest_fog", "Foltest: King of Temeria")
leader("gwent_leader_wolf", "northern", "leader_foltest_clear_weather", "Foltest: Lord Commander of the North")
leader("gwent_leader_foltest_siegemaster", "northern", "leader_foltest_siege_horn", "Foltest: The Siegemaster")
leader("gwent_leader_foltest_steel_forged", "northern", "leader_foltest_siege_scorch", "Foltest: The Steel-Forged")
leader("gwent_leader_emhyr_emperor", "nilfgaard", "leader_emhyr_spy_hand", "Emhyr var Emreis: Emperor of Nilfgaard")
leader("gwent_leader_emhyr_imperial", "nilfgaard", "leader_emhyr_rain", "Emhyr var Emreis: His Imperial Majesty")
leader("gwent_leader_nilfgaard", "nilfgaard", "leader_emhyr_graveyard_theft", "Emhyr var Emreis: The Relentless")
leader("gwent_leader_emhyr_white_flame", "nilfgaard", "leader_emhyr_cancel_leader", "Emhyr var Emreis: The White Flame")
leader("gwent_leader_francesca_daisy", "scoiatael", "leader_francesca_draw", "Francesca Findabair: Daisy of the Valley")
leader("gwent_leader_francesca_pureblood", "scoiatael", "leader_francesca_frost", "Francesca Findabair: Pureblood Elf")
leader("gwent_leader_francesca_queen", "scoiatael", "leader_francesca_melee_scorch", "Francesca Findabair: Queen of Dol Blathanna")
leader("gwent_leader_scoiatael", "scoiatael", "leader_francesca_ranged_horn", "Francesca Findabair: The Beautiful")
leader("gwent_leader_eredin_bringer", "monsters", "leader_eredin_graveyard_return", "Eredin: Bringer of Death")
leader("gwent_leader_monsters", "monsters", "leader_eredin_melee_horn", "Eredin: Commander of the Red Riders")
leader("gwent_leader_eredin_destroyer", "monsters", "leader_eredin_discard_draw", "Eredin: Destroyer of Worlds")
leader("gwent_leader_eredin_king", "monsters", "leader_eredin_weather", "Eredin: King of the Wild Hunt")

# Northern Realms.
add("gwent_unit_13", "northern", "siege", "unit", 6, display_name="Ballista")
copies("nr_blue_stripes_commando", 3, "northern", "melee", 4, "tight_bond", display_name="Blue Stripes Commando", name_group="blue_stripes_commando", bond_group="blue_stripes_commando", first_id="gwent_unit_03")
copies("nr_catapult", 2, "northern", "siege", 8, "tight_bond", display_name="Catapult", name_group="catapult", bond_group="catapult", first_id="gwent_unit_16")
copies("nr_crinfrid_reavers_dragon_hunter", 3, "northern", "ranged", 5, "tight_bond", display_name="Crinfrid Reavers Dragon Hunter", name_group="crinfrid_reavers_dragon_hunter", bond_group="crinfrid_reavers_dragon_hunter", first_id="gwent_unit_12")
add("gwent_unit_10", "northern", "ranged", "unit", 6, display_name="Dethmold")
add("gwent_unit_09", "northern", "siege", "unit", 5, "medic", rarity="Uncommon", display_name="Dun Banner Medic")
add("nr_esterad_thyssen", "northern", "melee", "unit", 10, "hero", rarity="Hero", display_name="Esterad Thyssen")
add("nr_john_natalis", "northern", "melee", "unit", 10, "hero", rarity="Hero", display_name="John Natalis")
copies("nr_kaedweni_siege_expert", 3, "northern", "siege", 1, "morale", display_name="Kaedweni Siege Expert", first_id="gwent_unit_05")
add("gwent_unit_07", "northern", "ranged", "unit", 5, display_name="Keira Metz")
add("nr_philippa_eilhart", "northern", "ranged", "unit", 10, "hero", rarity="Hero", display_name="Philippa Eilhart")
copies("nr_poor_fucking_infantry", 3, "northern", "melee", 1, "tight_bond", display_name="Poor Fucking Infantry", name_group="poor_fucking_infantry", bond_group="poor_fucking_infantry")
add("gwent_unit_06", "northern", "melee", "unit", 5, "spy", rarity="Uncommon", display_name="Prince Stennis")
add("gwent_unit_01", "northern", "melee", "unit", 1, display_name="Redanian Foot Soldier")
add("gwent_unit_08", "northern", "ranged", "unit", 4, display_name="Sabrina Glevissig")
add("nr_sheldon_skaggs", "northern", "ranged", "unit", 4, display_name="Sheldon Skaggs")
add("gwent_unit_11", "northern", "siege", "unit", 6, display_name="Siege Tower")
add("gwent_unit_02", "northern", "melee", "unit", 5, display_name="Siegfried of Denesle")
add("nr_sigismund_dijkstra", "northern", "melee", "unit", 4, "spy", rarity="Uncommon", display_name="Sigismund Dijkstra")
add("nr_sile_de_tansarville", "northern", "ranged", "unit", 5, display_name="Sile de Tansarville")
add("nr_thaler", "northern", "siege", "unit", 1, "spy", rarity="Uncommon", display_name="Thaler")
copies("nr_trebuchet", 2, "northern", "siege", 6, "none", display_name="Trebuchet", first_id="gwent_unit_14")
add("nr_vernon_roche", "northern", "melee", "unit", 10, "hero", rarity="Hero", display_name="Vernon Roche")
add("nr_ves", "northern", "melee", "unit", 5, display_name="Ves")
add("nr_yarpen_zigrin", "northern", "melee", "unit", 2, display_name="Yarpen Zigrin")

# Nilfgaard.
add("ng_albrich", "nilfgaard", "ranged", "unit", 2, display_name="Albrich")
add("ng_assire_var_anahid", "nilfgaard", "ranged", "unit", 6, display_name="Assire var Anahid")
copies("ng_black_infantry_archer", 2, "nilfgaard", "ranged", 10, "none", display_name="Black Infantry Archer")
add("ng_cahir", "nilfgaard", "melee", "unit", 6, display_name="Cahir Mawr Dyffryn aep Ceallach")
add("ng_cynthia", "nilfgaard", "ranged", "unit", 4, display_name="Cynthia")
copies("ng_etolian_auxiliary_archers", 2, "nilfgaard", "ranged", 1, "medic", display_name="Etolian Auxiliary Archers")
add("ng_fringilla_vigo", "nilfgaard", "ranged", "unit", 6, display_name="Fringilla Vigo")
add("ng_heavy_zerrikanian_fire_scorpion", "nilfgaard", "siege", "unit", 10, display_name="Heavy Zerrikanian Fire Scorpion")
copies("ng_impera_brigade_guard", 4, "nilfgaard", "melee", 3, "tight_bond", display_name="Impera Brigade Guard", name_group="impera_brigade_guard", bond_group="impera_brigade_guard")
add("ng_letho_of_gulet", "nilfgaard", "melee", "unit", 10, "hero", rarity="Hero", display_name="Letho of Gulet")
add("ng_menno_coehoorn", "nilfgaard", "melee", "unit", 10, "hero", rarity="Hero", tags="medic", display_name="Menno Coehoorn")
add("ng_morteisen", "nilfgaard", "melee", "unit", 3, display_name="Morteisen")
add("ng_morvran_voorhis", "nilfgaard", "siege", "unit", 10, "hero", rarity="Hero", display_name="Morvran Voorhis")
copies("ng_nausicaa_cavalry_rider", 3, "nilfgaard", "melee", 2, "tight_bond", display_name="Nausicaa Cavalry Rider", name_group="nausicaa_cavalry_rider", bond_group="nausicaa_cavalry_rider")
add("ng_puttkammer", "nilfgaard", "ranged", "unit", 3, display_name="Puttkammer")
add("ng_rainfarn", "nilfgaard", "melee", "unit", 4, display_name="Rainfarn")
add("ng_renuald_aep_matsen", "nilfgaard", "ranged", "unit", 5, display_name="Renuald aep Matsen")
add("ng_rotten_mangonel", "nilfgaard", "siege", "unit", 3, display_name="Rotten Mangonel")
add("gwent_unit_21", "nilfgaard", "melee", "unit", 7, "spy", rarity="Uncommon", display_name="Shilard Fitz-Oesterlen")
copies("ng_siege_engineer", 2, "nilfgaard", "siege", 6, "none", display_name="Siege Engineer")
add("gwent_unit_22", "nilfgaard", "siege", "unit", 0, "medic", rarity="Uncommon", display_name="Siege Technician")
add("ng_stefan_skellen", "nilfgaard", "melee", "unit", 9, "spy", rarity="Uncommon", display_name="Stefan Skellen")
add("ng_sweers", "nilfgaard", "ranged", "unit", 2, display_name="Sweers")
add("ng_tibor_eggebracht", "nilfgaard", "ranged", "unit", 10, "hero", rarity="Hero", display_name="Tibor Eggebracht")
add("ng_vanhemar", "nilfgaard", "ranged", "unit", 4, display_name="Vanhemar")
add("ng_vattier_de_rideaux", "nilfgaard", "melee", "unit", 4, "spy", rarity="Uncommon", display_name="Vattier de Rideaux")
add("ng_vreemde", "nilfgaard", "melee", "unit", 2, display_name="Vreemde")
copies("ng_young_emissary", 2, "nilfgaard", "melee", 5, "tight_bond", display_name="Young Emissary", name_group="young_emissary", bond_group="young_emissary")
add("ng_zerrikanian_fire_scorpion", "nilfgaard", "siege", "unit", 5, display_name="Zerrikanian Fire Scorpion")

# Scoia'tael.
add("gwent_unit_17", "scoiatael", "melee", "unit", 6, "agile", display_name="Barclay Els")
add("sc_ciaran", "scoiatael", "melee", "unit", 3, "agile", display_name="Ciaran aep Easnillien")
add("sc_dennis_cranmer", "scoiatael", "melee", "unit", 6, display_name="Dennis Cranmer")
add("sc_dol_blathanna_archer", "scoiatael", "ranged", "unit", 4, display_name="Dol Blathanna Archer")
copies("sc_dol_blathanna_scout", 3, "scoiatael", "melee", 6, "agile", display_name="Dol Blathanna Scout")
copies("sc_dwarven_skirmisher", 3, "scoiatael", "melee", 3, "muster", display_name="Dwarven Skirmisher", muster_group="dwarven_skirmisher", first_id="gwent_unit_18")
add("sc_eithne", "scoiatael", "ranged", "unit", 10, "hero", rarity="Hero", display_name="Eithne")
copies("sc_elven_skirmisher", 3, "scoiatael", "ranged", 2, "muster", display_name="Elven Skirmisher", muster_group="elven_skirmisher")
add("sc_filavandrel", "scoiatael", "melee", "unit", 6, "agile", display_name="Filavandrel aen Fidhail")
copies("sc_havekar_healer", 3, "scoiatael", "ranged", 0, "medic", display_name="Havekar Healer")
copies("sc_havekar_smuggler", 3, "scoiatael", "melee", 5, "muster", display_name="Havekar Smuggler", muster_group="havekar_smuggler")
add("sc_ida_emean", "scoiatael", "ranged", "unit", 6, display_name="Ida Emean aep Sivney")
add("sc_iorveth", "scoiatael", "ranged", "unit", 10, "hero", rarity="Hero", display_name="Iorveth")
add("rare_gwent_01", "scoiatael", "melee", "unit", 10, "hero", rarity="Hero", tags="morale", display_name="Isengrim Faoiltiarna")
copies("sc_mahakaman_defender", 5, "scoiatael", "melee", 5, "none", display_name="Mahakaman Defender")
add("sc_milva", "scoiatael", "ranged", "unit", 10, "morale", rarity="Uncommon", display_name="Milva")
add("sc_riordain", "scoiatael", "ranged", "unit", 1, display_name="Riordain")
add("sc_saesenthessis", "scoiatael", "ranged", "unit", 10, "hero", rarity="Hero", display_name="Saesenthessis")
add("sc_toruviel", "scoiatael", "ranged", "unit", 2, display_name="Toruviel")
add("sc_vrihedd_brigade_recruit", "scoiatael", "ranged", "unit", 4, display_name="Vrihedd Brigade Recruit")
copies("sc_vrihedd_brigade_veteran", 2, "scoiatael", "melee", 5, "agile", display_name="Vrihedd Brigade Veteran")
add("sc_yaevinn", "scoiatael", "melee", "unit", 6, "agile", display_name="Yaevinn")

# Monsters.
copies("mo_arachas", 3, "monsters", "melee", 4, "muster", display_name="Arachas", muster_group="arachas")
add("mo_arachas_behemoth", "monsters", "siege", "unit", 6, "muster", muster_group="arachas", display_name="Arachas Behemoth")
add("mo_botchling", "monsters", "melee", "unit", 4, display_name="Botchling")
add("mo_celaeno_harpy", "monsters", "melee", "unit", 2, "agile", display_name="Celaeno Harpy")
add("mo_cockatrice", "monsters", "ranged", "unit", 2, display_name="Cockatrice")
add("mo_crone_brewess", "monsters", "melee", "unit", 6, "muster", muster_group="crones", display_name="Crone: Brewess")
add("mo_crone_weavess", "monsters", "melee", "unit", 6, "muster", muster_group="crones", display_name="Crone: Weavess")
add("mo_crone_whispess", "monsters", "melee", "unit", 6, "muster", muster_group="crones", display_name="Crone: Whispess")
add("mo_draug", "monsters", "melee", "unit", 10, "hero", rarity="Hero", display_name="Draug")
add("mo_earth_elemental", "monsters", "siege", "unit", 6, display_name="Earth Elemental")
add("mo_endrega", "monsters", "ranged", "unit", 2, display_name="Endrega")
add("mo_fiend", "monsters", "melee", "unit", 6, display_name="Fiend")
add("mo_fire_elemental", "monsters", "siege", "unit", 6, display_name="Fire Elemental")
add("mo_foglet", "monsters", "melee", "unit", 2, display_name="Foglet")
add("mo_forktail", "monsters", "melee", "unit", 5, display_name="Forktail")
add("mo_frightener", "monsters", "melee", "unit", 5, display_name="Frightener")
add("mo_gargoyle", "monsters", "ranged", "unit", 2, display_name="Gargoyle")
copies("mo_ghoul", 3, "monsters", "melee", 1, "muster", display_name="Ghoul", muster_group="ghoul")
add("mo_grave_hag", "monsters", "ranged", "unit", 5, display_name="Grave Hag")
add("mo_griffin", "monsters", "melee", "unit", 5, display_name="Griffin")
add("mo_harpy", "monsters", "melee", "unit", 2, "agile", display_name="Harpy")
add("mo_ice_giant", "monsters", "siege", "unit", 5, display_name="Ice Giant")
add("mo_imlerith", "monsters", "melee", "unit", 10, "hero", rarity="Hero", display_name="Imlerith")
add("mo_kayran", "monsters", "melee", "unit", 8, "hero", rarity="Hero", tags="morale;agile", display_name="Kayran")
add("mo_leshen", "monsters", "ranged", "unit", 10, "hero", rarity="Hero", display_name="Leshen")
add("gwent_unit_19", "monsters", "melee", "unit", 2, "muster", muster_group="nekker", name_group="mo_nekker", display_name="Nekker")
add("gwent_unit_20", "monsters", "melee", "unit", 2, "muster", muster_group="nekker", name_group="mo_nekker", display_name="Nekker")
add("mo_nekker_3", "monsters", "melee", "unit", 2, "muster", muster_group="nekker", name_group="mo_nekker", display_name="Nekker")
add("mo_plague_maiden", "monsters", "melee", "unit", 5, display_name="Plague Maiden")
add("mo_vampire_bruxa", "monsters", "melee", "unit", 4, "muster", muster_group="vampire", display_name="Vampire: Bruxa")
add("mo_vampire_ekimmara", "monsters", "melee", "unit", 4, "muster", muster_group="vampire", display_name="Vampire: Ekimmara")
add("mo_vampire_fleder", "monsters", "melee", "unit", 4, "muster", muster_group="vampire", display_name="Vampire: Fleder")
add("mo_vampire_garkain", "monsters", "melee", "unit", 4, "muster", muster_group="vampire", display_name="Vampire: Garkain")
add("mo_vampire_katakan", "monsters", "melee", "unit", 5, "muster", muster_group="vampire", display_name="Vampire: Katakan")
add("mo_werewolf", "monsters", "melee", "unit", 5, display_name="Werewolf")
add("mo_wyvern", "monsters", "ranged", "unit", 2, display_name="Wyvern")

# Neutral base-game cards.
special_copies("neutral_biting_frost", 3, "weather", "weather_melee", display_name="Biting Frost", first_id="gwent_weather_frost")
special_copies("neutral_clear_weather", 3, "special", "clear_weather", display_name="Clear Weather", first_id="gwent_clear_weather")
special_copies("neutral_commanders_horn", 4, "special", "commanders_horn", display_name="Commander's Horn", first_id="gwent_horn")
special_copies("neutral_decoy", 3, "special", "decoy", display_name="Decoy", first_id="gwent_decoy")
add("neutral_emiel_regis", "neutral", "melee", "unit", 5, display_name="Emiel Regis Rohellec Terzieff")
add("rare_gwent_03", "neutral", "melee", "unit", 15, "hero", rarity="Hero", display_name="Cirilla Fiona Elen Riannon")
add("rare_gwent_02", "neutral", "melee", "unit", 15, "hero", rarity="Hero", display_name="Geralt of Rivia")
special_copies("neutral_impenetrable_fog", 3, "weather", "weather_ranged", display_name="Impenetrable Fog", first_id="gwent_weather_fog")
add("rare_gwent_04", "neutral", "melee", "unit", 0, "hero", rarity="Hero", tags="spy", display_name="Mysterious Elf")
special_copies("neutral_scorch", 3, "special", "scorch", display_name="Scorch", first_id="gwent_scorch")
special_copies("neutral_torrential_rain", 3, "weather", "weather_siege", display_name="Torrential Rain", first_id="gwent_weather_rain")
add("neutral_triss", "neutral", "melee", "unit", 7, "hero", rarity="Hero", display_name="Triss Merigold")
add("neutral_vesemir", "neutral", "melee", "unit", 6, display_name="Vesemir")
add("rare_gwent_06", "neutral", "melee", "unit", 2, "commanders_horn", rarity="Uncommon", display_name="Dandelion")
add("neutral_villentretenmerth", "neutral", "melee", "unit", 7, "scorch_melee", rarity="Uncommon", display_name="Villentretenmerth")
add("rare_gwent_05", "neutral", "ranged", "unit", 7, "hero", rarity="Hero", tags="medic", display_name="Yennefer of Vengerberg")
add("neutral_zoltan", "neutral", "melee", "unit", 5, display_name="Zoltan Chivay")


DEFAULT_SPECIAL_CARD_IDS = [
    "gwent_weather_frost",
    "gwent_weather_fog",
    "gwent_weather_rain",
    "gwent_clear_weather",
    "gwent_horn",
    "neutral_commanders_horn_2",
    "gwent_decoy",
    "neutral_decoy_2",
    "gwent_scorch",
    "neutral_scorch_2",
]


COMPAT_DECK_IDS = {
    ("p_witcher_1", "northern"): "deck_witcher_wolf",
    ("p_witcher_1", "nilfgaard"): "deck_witcher_wolf_nilfgaard",
    ("p_witcher_1", "scoiatael"): "deck_witcher_wolf_scoiatael",
    ("p_witcher_1", "monsters"): "deck_witcher_wolf_monsters",
    ("p_witcher_2", "northern"): "deck_witcher_cat",
}


def faction_cards(faction: str) -> list[str]:
    unit_cards = [
        card.card_id
        for card in cards
        if card.faction in {faction, "neutral"} and card.type == "unit"
    ]
    return [*unit_cards, *DEFAULT_SPECIAL_CARD_IDS]


def deck_id_for(player_id: str, faction: str) -> str:
    return COMPAT_DECK_IDS.get((player_id, faction), f"deck_{player_id}_{faction}")


def all_card_count_by_id() -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for card in cards:
        counts[card.card_id] += 1
    return counts


def assert_catalog_integrity() -> None:
    duplicate_ids = sorted(card_id for card_id, count in all_card_count_by_id().items() if count > 1)
    if duplicate_ids:
        raise ValueError(f"Duplicate Gwent card ids: {', '.join(duplicate_ids)}")
    for faction in ["northern", "nilfgaard", "scoiatael", "monsters"]:
        deck_cards = faction_cards(faction)
        special_count = sum(1 for card_id in deck_cards if next(card for card in cards if card.card_id == card_id).type == "special")
        unit_count = sum(1 for card_id in deck_cards if next(card for card in cards if card.card_id == card_id).type == "unit")
        if unit_count < 22:
            raise ValueError(f"{faction} generated deck has only {unit_count} unit cards")
        if special_count > 10:
            raise ValueError(f"{faction} generated deck has {special_count} special cards")


def collection_card_ids(faction: str) -> list[str]:
    return [
        card.card_id
        for card in cards
        if card.faction in {faction, "neutral"} and card.type != "leader"
    ]


def write_cards() -> None:
    path = SEED_DIR / "gwent_cards.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CARD_FIELDS, lineterminator="\n")
        writer.writeheader()
        for card in cards:
            writer.writerow(card.row_dict())


def write_decks() -> None:
    player_ids = [
        "p_witcher_1",
        "p_witcher_2",
        "p_witcher_3",
        "p_witcher_4",
        "p_witcher_5",
        "p_sorc_1",
        "p_sorc_2",
        "p_sorc_3",
        "p_sorc_4",
    ]
    deck_specs = [
        ("northern", "gwent_leader_wolf"),
        ("nilfgaard", "gwent_leader_nilfgaard"),
        ("scoiatael", "gwent_leader_scoiatael"),
        ("monsters", "gwent_leader_monsters"),
    ]
    with (SEED_DIR / "gwent_decks.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["deck_id", "player_id", "leader_card_id", "card_ids"],
            lineterminator="\n",
        )
        writer.writeheader()
        for player_id in player_ids:
            for faction, leader_id in deck_specs:
                writer.writerow(
                    {
                        "deck_id": deck_id_for(player_id, faction),
                        "player_id": player_id,
                        "leader_card_id": leader_id,
                        "card_ids": ";".join(faction_cards(faction)),
                    }
                )


def write_checklist() -> None:
    by_faction: dict[str, list[Card]] = defaultdict(list)
    for card in cards:
        by_faction[card.faction].append(card)

    lines = [
        "# Чеклист карт базового Гвинта Witcher 3",
        "",
        "Первая итерация: 4 базовые стороны без Скеллиге, Hearts of Stone, Blood and Wine и post-release reward-карт.",
        "Одна строка в `data/seed/gwent_cards.csv` соответствует одной физической карте. Повторяющиеся карты имеют разные `card_id`, но общий `display_name` и группы связки/сбора.",
        "",
        "## Сводка",
        "",
    ]
    for faction in ["northern", "nilfgaard", "scoiatael", "monsters", "neutral"]:
        faction_cards_list = by_faction[faction]
        leaders = sum(1 for card in faction_cards_list if card.type == "leader")
        units = sum(1 for card in faction_cards_list if card.type == "unit")
        specials = sum(1 for card in faction_cards_list if card.type == "special")
        lines.append(f"- [x] {label_faction(faction)}: {len(faction_cards_list)} карт; лидеры {leaders}; отряды {units}; спец/погода {specials}.")
    lines.extend(["", "## Карты", ""])
    for faction in ["northern", "nilfgaard", "scoiatael", "monsters", "neutral"]:
        lines.extend([f"### {label_faction(faction)}", ""])
        grouped: dict[str, list[Card]] = defaultdict(list)
        for card in by_faction[faction]:
            grouped[card.display_name].append(card)
        for display_name in sorted(grouped):
            group = grouped[display_name]
            sample = group[0]
            count = len(group)
            suffix = f" x{count}" if count > 1 else ""
            lines.append(
                f"- [x] {display_name}{suffix} - {label_type(sample)}; {label_row(sample.row)}; сила {sample.strength}; {label_effects(sample)}."
            )
        lines.append("")
    lines.extend(
        [
            "## Не входит в первую итерацию",
            "",
            "- [ ] Скеллиге и все карты Blood and Wine.",
            "- [ ] Карты Hearts of Stone: Cow, Bovine Defense Force, Gaunter O'Dimm, Gaunter O'Dimm: Darkness, Olgierd von Everec, Toad, Schirru и лидеры из дополнения.",
            "- [ ] Post-release reward-карты и эффекты Roach-muster у Geralt/Ciri.",
            "",
        ]
    )
    CHECKLIST_PATH.write_text("\n".join(lines), encoding="utf-8")


def label_faction(faction: str) -> str:
    return {
        "northern": "Королевства Севера",
        "nilfgaard": "Нильфгаард",
        "scoiatael": "Скоя'таэли",
        "monsters": "Чудовища",
        "neutral": "Нейтральные",
    }[faction]


def label_type(card: Card) -> str:
    if card.type == "leader":
        return "лидер"
    if card.type == "special":
        return "спецкарта"
    if card.effect == "hero" or "hero" in split_tags(card.ability_tags):
        return "герой"
    return "отряд"


def label_row(row: str) -> str:
    return {
        "leader": "лидер",
        "melee": "ближний ряд",
        "ranged": "дальний ряд",
        "siege": "осадный ряд",
        "weather": "погода",
        "special": "без ряда",
    }.get(row, row)


def label_effects(card: Card) -> str:
    effects = [card.effect, *split_tags(card.ability_tags)]
    readable = {
        "none": "без эффекта",
        "hero": "герой",
        "spy": "шпион",
        "medic": "лекарь",
        "muster": "сбор",
        "morale": "боевой дух",
        "tight_bond": "связка",
        "agile": "гибкая",
        "weather_melee": "мороз",
        "weather_ranged": "туман",
        "weather_siege": "ливень",
        "clear_weather": "ясная погода",
        "commanders_horn": "командирский рог",
        "decoy": "чучело",
        "scorch": "казнь",
        "scorch_melee": "казнь ближнего ряда",
        "leader_foltest_fog": "лидер: туман",
        "leader_foltest_clear_weather": "лидер: ясная погода",
        "leader_foltest_siege_horn": "лидер: рог осады",
        "leader_foltest_siege_scorch": "лидер: казнь осады",
        "leader_emhyr_spy_hand": "лидер: разведка руки",
        "leader_emhyr_rain": "лидер: ливень",
        "leader_emhyr_graveyard_theft": "лидер: карта из чужого сброса",
        "leader_emhyr_cancel_leader": "лидер: отмена лидера",
        "leader_francesca_draw": "лидер: дополнительная карта",
        "leader_francesca_frost": "лидер: мороз",
        "leader_francesca_melee_scorch": "лидер: казнь ближнего ряда",
        "leader_francesca_ranged_horn": "лидер: рог дальнего ряда",
        "leader_eredin_graveyard_return": "лидер: вернуть карту из сброса",
        "leader_eredin_melee_horn": "лидер: рог ближнего ряда",
        "leader_eredin_discard_draw": "лидер: сброс и добор",
        "leader_eredin_weather": "лидер: погода",
    }
    labels = [readable.get(effect, effect) for effect in effects if effect]
    return "; ".join(labels) if labels else "без эффекта"


def main() -> None:
    assert_catalog_integrity()
    write_cards()
    write_decks()
    write_checklist()


if __name__ == "__main__":
    main()
