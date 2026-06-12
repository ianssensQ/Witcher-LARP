"""Shared ownership and lock helpers for reward, trade and stake assets."""

from __future__ import annotations

from datetime import UTC, datetime
import json
import re
import sqlite3
from typing import Any

from .runtime_schema import ensure_runtime_schema


ASSET_TYPES = {"item", "card", "artifact", "potion", "order_object", "final_object"}
OWNERSHIP_ASSET_TYPES = ASSET_TYPES - {"potion"}
ACTIVE_LOCK_STATUS = "active"
FINAL_LOCK_STATUSES = {"released", "consumed"}


class AssetContractError(ValueError):
    """Business-rule failure for asset ownership and lock transitions."""

    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def ensure_asset_contract_schema(connection: sqlite3.Connection) -> None:
    ensure_runtime_schema(connection)
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS reward_approvals (
            approval_id TEXT PRIMARY KEY,
            reward_id TEXT NOT NULL,
            player_id TEXT,
            status TEXT NOT NULL,
            source_event_id INTEGER,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            decided_at TEXT
        );

        CREATE TABLE IF NOT EXISTS reward_approval_audit (
            audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
            approval_id TEXT NOT NULL,
            action TEXT NOT NULL,
            operator TEXT NOT NULL,
            reason TEXT NOT NULL,
            status_before TEXT,
            status_after TEXT NOT NULL,
            correction_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            FOREIGN KEY (approval_id) REFERENCES reward_approvals(approval_id)
        );

        CREATE TABLE IF NOT EXISTS asset_ownership (
            ownership_id TEXT PRIMARY KEY,
            owner_player_id TEXT NOT NULL,
            asset_type TEXT NOT NULL,
            asset_id TEXT NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 1,
            status TEXT NOT NULL DEFAULT 'active',
            source TEXT NOT NULL,
            source_ref_id TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(owner_player_id, asset_type, asset_id, status)
        );

        CREATE INDEX IF NOT EXISTS idx_asset_ownership_asset
        ON asset_ownership(asset_type, asset_id, status);

        CREATE TABLE IF NOT EXISTS asset_locks (
            lock_id TEXT PRIMARY KEY,
            owner_player_id TEXT,
            asset_type TEXT NOT NULL,
            asset_id TEXT NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 1,
            lock_type TEXT NOT NULL,
            source_ref_id TEXT NOT NULL,
            status TEXT NOT NULL,
            locked_at TEXT NOT NULL,
            released_at TEXT,
            reason TEXT,
            metadata_json TEXT NOT NULL DEFAULT '{}'
        );

        CREATE INDEX IF NOT EXISTS idx_asset_locks_asset
        ON asset_locks(asset_type, asset_id, status);
        """
    )
    _ensure_columns(
        connection,
        "reward_approvals",
        {
            "decided_by": "TEXT",
            "audit_reason": "TEXT",
            "correction_json": "TEXT NOT NULL DEFAULT '{}'",
            "applied_at": "TEXT",
            "locked_assets_json": "TEXT NOT NULL DEFAULT '[]'",
        },
    )
    _ensure_columns(
        connection,
        "trade_transfer_runtime",
        {
            "closed_at": "TEXT",
            "close_reason": "TEXT",
            "closed_by_player_id": "TEXT",
        },
    )


def reward_asset_entries(
    connection: sqlite3.Connection,
    reward_id: str,
    correction: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    reward = _reward_row(connection, reward_id)
    correction = correction or {}
    entries: list[dict[str, Any]] = []
    for key, asset_type in (
        ("item_ids", "item"),
        ("card_ids", "card"),
        ("artifact_ids", "artifact"),
    ):
        raw_value = correction.get(key, reward[key])
        for asset_id in _split_ids(raw_value):
            entries.append(
                {
                    "asset_type": asset_type,
                    "asset_id": asset_id,
                    "quantity": 1,
                    "reward_id": reward_id,
                }
            )
    return entries


def reward_numeric_payload(
    connection: sqlite3.Connection,
    reward_id: str,
    correction: dict[str, Any] | None = None,
) -> dict[str, int]:
    reward = _reward_row(connection, reward_id)
    correction = correction or {}
    return {
        "xp": _to_int(correction.get("xp", reward["xp"])),
        "gold": _to_int(correction.get("gold", reward["gold"])),
    }


def lock_reward_assets(
    connection: sqlite3.Connection,
    *,
    approval_id: str,
    player_id: str,
    reward_id: str,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    ensure_asset_contract_schema(connection)
    timestamp = _iso(now)
    locked_assets = reward_asset_entries(connection, reward_id)
    for asset in locked_assets:
        _assert_asset_lock_available(
            connection,
            asset_type=str(asset["asset_type"]),
            asset_id=str(asset["asset_id"]),
            purpose="reward approval",
            allowed_lock_type="reward_approval",
            allowed_source_ref_id=approval_id,
        )
        lock_id = _lock_id("reward", approval_id, asset["asset_type"], asset["asset_id"])
        connection.execute(
            """
            INSERT INTO asset_locks (
                lock_id, owner_player_id, asset_type, asset_id, quantity,
                lock_type, source_ref_id, status, locked_at, reason, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, 'reward_approval', ?, ?, ?, ?, ?)
            ON CONFLICT(lock_id) DO NOTHING
            """,
            (
                lock_id,
                player_id,
                asset["asset_type"],
                asset["asset_id"],
                int(asset["quantity"]),
                approval_id,
                ACTIVE_LOCK_STATUS,
                timestamp,
                "reward requires master approval",
                _json_dumps({"approval_id": approval_id, "reward_id": reward_id}),
            ),
        )
    connection.execute(
        """
        UPDATE reward_approvals
        SET locked_assets_json = ?
        WHERE approval_id = ?
        """,
        (_json_dumps(locked_assets), approval_id),
    )
    return locked_assets


def assert_reward_assets_unlocked(
    connection: sqlite3.Connection,
    *,
    reward_id: str,
    purpose: str,
) -> None:
    ensure_asset_contract_schema(connection)
    for asset in reward_asset_entries(connection, reward_id):
        _assert_asset_lock_available(
            connection,
            asset_type=str(asset["asset_type"]),
            asset_id=str(asset["asset_id"]),
            purpose=purpose,
        )


def release_locks_for_source(
    connection: sqlite3.Connection,
    *,
    lock_type: str,
    source_ref_id: str,
    status: str = "released",
    reason: str,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    ensure_asset_contract_schema(connection)
    if status not in FINAL_LOCK_STATUSES:
        raise AssetContractError("invalid_lock_status", f"Unsupported lock release status: {status}.")
    timestamp = _iso(now)
    rows = active_locks_for_source(connection, lock_type=lock_type, source_ref_id=source_ref_id)
    connection.execute(
        """
        UPDATE asset_locks
        SET status = ?, released_at = ?, reason = ?
        WHERE lock_type = ? AND source_ref_id = ? AND status = ?
        """,
        (status, timestamp, reason, lock_type, source_ref_id, ACTIVE_LOCK_STATUS),
    )
    return rows


def active_locks_for_source(
    connection: sqlite3.Connection,
    *,
    lock_type: str,
    source_ref_id: str,
) -> list[dict[str, Any]]:
    ensure_asset_contract_schema(connection)
    return [
        _clean_row(row)
        for row in connection.execute(
            """
            SELECT *
            FROM asset_locks
            WHERE lock_type = ? AND source_ref_id = ? AND status = ?
            ORDER BY locked_at, lock_id
            """,
            (lock_type, source_ref_id, ACTIVE_LOCK_STATUS),
        ).fetchall()
    ]


def active_locks_for_asset(
    connection: sqlite3.Connection,
    *,
    asset_type: str,
    asset_id: str,
) -> list[dict[str, Any]]:
    ensure_asset_contract_schema(connection)
    return [
        _clean_row(row)
        for row in connection.execute(
            """
            SELECT *
            FROM asset_locks
            WHERE asset_type = ? AND asset_id = ? AND status = ?
            ORDER BY locked_at, lock_id
            """,
            (_asset_type(asset_type), asset_id, ACTIVE_LOCK_STATUS),
        ).fetchall()
    ]


def assert_asset_unlocked(
    connection: sqlite3.Connection,
    *,
    asset_type: str,
    asset_id: str,
    owner_player_id: str | None = None,
    purpose: str,
) -> None:
    normalized_type = _asset_type(asset_type)
    locks = active_locks_for_asset(connection, asset_type=normalized_type, asset_id=asset_id)
    if owner_player_id is not None and normalized_type == "potion":
        locks = [
            lock
            for lock in locks
            if lock.get("owner_player_id") in {None, "", owner_player_id}
        ]
    if locks:
        first = locks[0]
        raise AssetContractError(
            "asset_locked",
            (
                f"Asset {asset_type}:{asset_id} is locked for "
                f"{first.get('lock_type')} and cannot be used for {purpose}."
            ),
            409,
        )


def _assert_asset_lock_available(
    connection: sqlite3.Connection,
    *,
    asset_type: str,
    asset_id: str,
    purpose: str,
    allowed_lock_type: str | None = None,
    allowed_source_ref_id: str | None = None,
) -> None:
    normalized_type = _asset_type(asset_type)
    locks = active_locks_for_asset(
        connection,
        asset_type=normalized_type,
        asset_id=asset_id,
    )
    if allowed_lock_type is not None and allowed_source_ref_id is not None:
        locks = [
            lock
            for lock in locks
            if not (
                str(lock.get("lock_type")) == allowed_lock_type
                and str(lock.get("source_ref_id")) == allowed_source_ref_id
            )
        ]
    if locks:
        first = locks[0]
        raise AssetContractError(
            "asset_locked",
            (
                f"Asset {normalized_type}:{asset_id} is locked for "
                f"{first.get('lock_type')} and cannot be used for {purpose}."
            ),
            409,
        )


def grant_asset_ownership(
    connection: sqlite3.Connection,
    *,
    owner_player_id: str,
    asset_type: str,
    asset_id: str,
    quantity: int = 1,
    source: str,
    source_ref_id: str | None,
    now: datetime | None = None,
) -> dict[str, Any]:
    ensure_asset_contract_schema(connection)
    normalized_type = _asset_type(asset_type)
    if normalized_type == "potion":
        raise AssetContractError("potion_ownership_external", "Potion ownership is stored in potion_inventory.")
    if quantity <= 0:
        raise AssetContractError("invalid_quantity", "Asset quantity must be positive.")
    timestamp = _iso(now)
    ownership_id = _ownership_id(owner_player_id, normalized_type, asset_id)
    connection.execute(
        """
        INSERT INTO asset_ownership (
            ownership_id, owner_player_id, asset_type, asset_id, quantity,
            status, source, source_ref_id, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, 'active', ?, ?, ?, ?)
        ON CONFLICT(owner_player_id, asset_type, asset_id, status) DO UPDATE SET
            quantity = asset_ownership.quantity + excluded.quantity,
            source = excluded.source,
            source_ref_id = excluded.source_ref_id,
            updated_at = excluded.updated_at
        """,
        (
            ownership_id,
            owner_player_id,
            normalized_type,
            asset_id,
            int(quantity),
            source,
            source_ref_id,
            timestamp,
            timestamp,
        ),
    )
    return ownership_for_asset(
        connection,
        owner_player_id=owner_player_id,
        asset_type=normalized_type,
        asset_id=asset_id,
    )


def debit_asset_ownership(
    connection: sqlite3.Connection,
    *,
    owner_player_id: str,
    asset_type: str,
    asset_id: str,
    quantity: int = 1,
    now: datetime | None = None,
) -> dict[str, Any]:
    ensure_asset_contract_schema(connection)
    normalized_type = _asset_type(asset_type)
    if normalized_type == "potion":
        raise AssetContractError("potion_ownership_external", "Potion ownership is stored in potion_inventory.")
    if quantity <= 0:
        raise AssetContractError("invalid_quantity", "Asset quantity must be positive.")
    timestamp = _iso(now)
    before = ownership_for_asset(
        connection,
        owner_player_id=owner_player_id,
        asset_type=normalized_type,
        asset_id=asset_id,
    )
    if before["quantity"] < quantity:
        raise AssetContractError(
            "asset_owner_mismatch",
            f"{owner_player_id} does not own enough {normalized_type}:{asset_id}.",
            409,
        )
    connection.execute(
        """
        UPDATE asset_ownership
        SET quantity = quantity - ?, updated_at = ?
        WHERE owner_player_id = ? AND asset_type = ? AND asset_id = ? AND status = 'active'
        """,
        (quantity, timestamp, owner_player_id, normalized_type, asset_id),
    )
    connection.execute(
        """
        DELETE FROM asset_ownership
        WHERE owner_player_id = ?
          AND asset_type = ?
          AND asset_id = ?
          AND status = 'active'
          AND quantity <= 0
        """,
        (owner_player_id, normalized_type, asset_id),
    )
    return ownership_for_asset(
        connection,
        owner_player_id=owner_player_id,
        asset_type=normalized_type,
        asset_id=asset_id,
    )


def lock_owned_asset(
    connection: sqlite3.Connection,
    *,
    lock_id: str,
    owner_player_id: str,
    asset_type: str,
    asset_id: str,
    quantity: int = 1,
    lock_type: str,
    source_ref_id: str,
    reason: str,
    require_existing_owner: bool = True,
    now: datetime | None = None,
) -> dict[str, Any]:
    ensure_asset_contract_schema(connection)
    normalized_type = _asset_type(asset_type)
    if quantity <= 0:
        raise AssetContractError("invalid_quantity", "Asset quantity must be positive.")
    assert_asset_unlocked(
        connection,
        asset_type=normalized_type,
        asset_id=asset_id,
        owner_player_id=owner_player_id,
        purpose=lock_type,
    )
    before = ownership_for_asset(
        connection,
        owner_player_id=owner_player_id,
        asset_type=normalized_type,
        asset_id=asset_id,
    )
    if normalized_type in OWNERSHIP_ASSET_TYPES and (require_existing_owner or before["quantity"] > 0):
        debit_asset_ownership(
            connection,
            owner_player_id=owner_player_id,
            asset_type=normalized_type,
            asset_id=asset_id,
            quantity=quantity,
            now=now,
        )
    timestamp = _iso(now)
    connection.execute(
        """
        INSERT INTO asset_locks (
            lock_id, owner_player_id, asset_type, asset_id, quantity,
            lock_type, source_ref_id, status, locked_at, reason, metadata_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            lock_id,
            owner_player_id,
            normalized_type,
            asset_id,
            int(quantity),
            lock_type,
            source_ref_id,
            ACTIVE_LOCK_STATUS,
            timestamp,
            reason,
            _json_dumps({"ownership_quantity_before": before["quantity"]}),
        ),
    )
    return _clean_row(
        connection.execute("SELECT * FROM asset_locks WHERE lock_id = ?", (lock_id,)).fetchone()
    )


def settle_owned_asset_lock(
    connection: sqlite3.Connection,
    *,
    lock_type: str,
    source_ref_id: str,
    target_player_id: str | None,
    final_status: str,
    reason: str,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    ensure_asset_contract_schema(connection)
    if final_status not in FINAL_LOCK_STATUSES:
        raise AssetContractError("invalid_lock_status", f"Unsupported lock settlement: {final_status}.")
    rows = active_locks_for_source(connection, lock_type=lock_type, source_ref_id=source_ref_id)
    for row in rows:
        asset_type = str(row["asset_type"])
        if asset_type in OWNERSHIP_ASSET_TYPES:
            owner = target_player_id if final_status == "consumed" else str(row["owner_player_id"])
            if owner:
                grant_asset_ownership(
                    connection,
                    owner_player_id=owner,
                    asset_type=asset_type,
                    asset_id=str(row["asset_id"]),
                    quantity=_to_int(row["quantity"]),
                    source=f"{lock_type}_{final_status}",
                    source_ref_id=source_ref_id,
                    now=now,
                )
    release_locks_for_source(
        connection,
        lock_type=lock_type,
        source_ref_id=source_ref_id,
        status=final_status,
        reason=reason,
        now=now,
    )
    return rows


def ownership_for_asset(
    connection: sqlite3.Connection,
    *,
    owner_player_id: str,
    asset_type: str,
    asset_id: str,
) -> dict[str, Any]:
    ensure_asset_contract_schema(connection)
    row = connection.execute(
        """
        SELECT *
        FROM asset_ownership
        WHERE owner_player_id = ? AND asset_type = ? AND asset_id = ? AND status = 'active'
        """,
        (owner_player_id, _asset_type(asset_type), asset_id),
    ).fetchone()
    if row is None:
        return {
            "ownership_id": _ownership_id(owner_player_id, _asset_type(asset_type), asset_id),
            "owner_player_id": owner_player_id,
            "asset_type": _asset_type(asset_type),
            "asset_id": asset_id,
            "quantity": 0,
            "status": "active",
            "source": None,
            "source_ref_id": None,
            "created_at": None,
            "updated_at": None,
        }
    payload = _clean_row(row)
    payload["quantity"] = _to_int(payload["quantity"])
    return payload


def active_asset_locks(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    ensure_asset_contract_schema(connection)
    return [
        _clean_row(row)
        for row in connection.execute(
            """
            SELECT *
            FROM asset_locks
            WHERE status = ?
            ORDER BY locked_at, lock_id
            """,
            (ACTIVE_LOCK_STATUS,),
        ).fetchall()
    ]


def active_reward_approvals(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    ensure_asset_contract_schema(connection)
    return [
        _approval_payload(row)
        for row in connection.execute(
            """
            SELECT *
            FROM reward_approvals
            WHERE status = 'pending_master_approval'
            ORDER BY created_at, approval_id
            """
        ).fetchall()
    ]


def _reward_row(connection: sqlite3.Connection, reward_id: str) -> sqlite3.Row:
    row = connection.execute(
        """
        SELECT *
        FROM rewards
        WHERE reward_id = ?
        """,
        (reward_id,),
    ).fetchone()
    if row is None:
        raise AssetContractError("unknown_reward", f"Unknown reward_id: {reward_id}.", 404)
    return row


def _approval_payload(row: sqlite3.Row) -> dict[str, Any]:
    payload = _clean_row(row)
    payload["correction"] = _json_loads(payload.get("correction_json"), {})
    payload["locked_assets"] = _json_loads(payload.get("locked_assets_json"), [])
    return payload


def _asset_type(asset_type: str) -> str:
    normalized = str(asset_type).strip().lower()
    if normalized not in ASSET_TYPES:
        raise AssetContractError("unsupported_asset_type", f"Unsupported asset_type: {asset_type}.")
    return normalized


def _ownership_id(owner_player_id: str, asset_type: str, asset_id: str) -> str:
    return _safe_id(f"own_{owner_player_id}_{asset_type}_{asset_id}")


def _lock_id(prefix: str, source_ref_id: str, asset_type: str, asset_id: str) -> str:
    return _safe_id(f"lock_{prefix}_{source_ref_id}_{asset_type}_{asset_id}")


def _safe_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]+", "_", value)


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
            connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")


def _split_ids(value: object) -> list[str]:
    if value is None:
        return []
    return [
        part.strip()
        for part in str(value).replace(",", ";").split(";")
        if part.strip()
    ]


def _clean_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        return {}
    return {key: row[key] for key in row.keys()}


def _json_dumps(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)


def _json_loads(value: object, fallback: Any) -> Any:
    try:
        if value in (None, ""):
            return fallback
        return json.loads(str(value))
    except json.JSONDecodeError:
        return fallback


def _to_int(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _iso(value: datetime | None = None) -> str:
    return (value or datetime.now(UTC)).isoformat(timespec="seconds")
