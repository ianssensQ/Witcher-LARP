"""Canonical player stat identifiers shared by seed validation and runtime."""

from __future__ import annotations


CANONICAL_STATS = ("Сила", "Ловкость", "Разум", "Харизма", "Воля")
CANONICAL_STAT_SET = frozenset(CANONICAL_STATS)
DEFAULT_STAT_ID = "Сила"
START_STAT_BUDGET = 7
START_STAT_MAX = 3
RUNTIME_STAT_MAX = 7

