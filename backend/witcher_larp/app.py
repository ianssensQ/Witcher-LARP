"""FastAPI application factory for the local game master server."""

from pathlib import Path
import socket
import sqlite3
from typing import Any

from .act_service import ActNotFoundError, UnlockCodeHiddenError
from .act_service import get_act_state, record_physical_announcement, reveal_unlock_code
from .act_service import set_active_act_elapsed_minutes, start_act
from .admin_content import build_handout_checklist, build_qr_checklist
from .admin_content import export_latest_snapshot, latest_import_report
from .admin_content import list_content_packs, resolve_manifest_path, resolve_snapshot_dir
from .admin_studio import build_admin_overview
from .asset_service import AssetContractError
from .backup_service import run_backup
from .config import PROJECT_ROOT, Settings
from .database import healthcheck_database, init_database
from .database import connect
from .final_summary_service import build_final_summary, record_final_master_note
from .game_ops_service import GameOpsCorrectionError
from .game_ops_service import apply_game_ops_correction, backup_status
from .game_ops_service import build_master_state, build_visibility_audit
from .game_ops_service import list_master_player_codes
from .import_service import DEFAULT_SNAPSHOT_DIR, import_seed_pack
from .lord_battle_service import LordBattleError
from .lord_battle_service import create_lord_battle, get_lord_battle, list_lord_battles
from .lord_battle_service import record_lord_battle_action
from .lord_panel import RoleTokenAuth, RoleTokenRequest, authenticate_role_token
from .lord_panel import build_lord_state, build_lord_summary_state
from .lord_runtime import LordRuntimeError
from .lord_runtime import buy_building, cleanse_raid_effect, move_lord, order_action
from .lord_runtime import ensure_lord_runtime_state
from .lord_runtime import preview_lord_route, recruit_action
from .lord_runtime import reconcile_pending_lord_moves
from .lord_runtime import start_raid, transfer_garrison
from .material_market_service import MaterialMarketError
from .material_market_service import ensure_material_market_runtime_state
from .material_market_service import sell_material_to_market
from .npc_service import NpcEventError, NpcEventInput
from .npc_service import list_npc_deals, list_npc_events, record_npc_event
from .npc_service import resolve_npc_event, review_queue
from .pvp_service import ChallengeCreateInput, ChallengeStartInput, PvpError
from .pvp_service import convert_personal_card_to_lord, create_pvp_challenge
from .pvp_service import GwentActionInput, GwentBotMatchInput, GwentDeckSaveInput, GwentPreparationInput
from .pvp_service import finish_gwent_match, get_player_pvp_state, get_pvp_tables
from .pvp_service import prepare_gwent_challenge, record_gwent_action, record_gwent_round, save_gwent_runtime_deck, start_gwent_bot_match
from .pvp_service import record_pvp_refusal, set_pvp_throttle_mode, start_pvp_challenge
from .qr_runtime import QrLookupRequest, has_qr_content, lookup_qr_runtime
from .qr_runtime import normalize_qr_code
from .reputation_service import ReputationError
from .reputation_service import apply_reputation_change, get_reputation_view
from .review_service import ReviewDecisionError, decide_event_review
from .reward_service import decide_reward_approval
from .sorceress_service import SorceressError
from .sorceress_service import accept_favorite, accept_trade_transfer, buy_potion
from .sorceress_service import cast_spell, create_favorite_request, create_trade_transfer
from .sorceress_service import decline_trade_transfer, get_sorceress_state
from .sorceress_service import ensure_sorceress_runtime_state
from .sorceress_service import record_alignment_evidence, transfer_potion
from .sorceress_service import use_potion_in_scene
from .snapshot_exporter import build_snapshot_from_database
from .timer_service import apply_due_timers, apply_manual_lord_income_tick, timer_status

try:
    from fastapi import FastAPI
    from fastapi import Header
    from fastapi import HTTPException
    from fastapi import Request
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import FileResponse, RedirectResponse
    from fastapi.staticfiles import StaticFiles
    from pydantic import BaseModel
except ModuleNotFoundError:  # pragma: no cover - exercised in dependency smoke tests.
    FastAPI = None  # type: ignore[assignment]
    HTTPException = None  # type: ignore[assignment]
    CORSMiddleware = None  # type: ignore[assignment]
    Request = object  # type: ignore[assignment,misc]
    BaseModel = object  # type: ignore[assignment,misc]


WEB_ROOT = Path(__file__).parent / "web"
ADMIN_STUDIO_INDEX = WEB_ROOT / "admin" / "index.html"
LORD_FRONTEND_DIST = PROJECT_ROOT / "prototypes" / "stage2b-v2" / "dist"
LORD_FRONTEND_INDEX = LORD_FRONTEND_DIST / "index.html"
LORD_FRONTEND_ASSETS = LORD_FRONTEND_DIST / "assets"
API_REVISION = "ios-gwent-pvp-v1"
API_FEATURES = (
    "ios_gwent_bot_match",
    "ios_gwent_deckbuilder",
    "ios_gwent_pvp_actions",
    "ios_gwent_preflight",
    "ios_gwent_scoiatael_first_turn",
)


class QrLookupPayload(BaseModel):
    code: str
    player_id: str | None = None
    device_id: str | None = None
    source: str = "manual_id"
    physical_presence_confirmed: bool = False


class QrOrderCheckPayload(BaseModel):
    code: str
    device_id: str | None = None
    source: str = "qr_scan"


class PlayerCodePayload(BaseModel):
    player_code: str
    device_id: str | None = None


class ActStartPayload(BaseModel):
    operator: str = "master"
    source: str = "master_api"
    physical_announcement_state: str = "announced"


class PhysicalAnnouncementPayload(BaseModel):
    operator: str = "master"
    source: str = "master_api"
    state: str = "announced"


class GameStartSetupPayload(BaseModel):
    operator: str = "master"
    source: str = "master_start_setup"
    act_id: str = "act1"
    physical_announcement_state: str = "announced"


class ActElapsedPayload(BaseModel):
    elapsed_minutes: int
    operator: str = "master"
    source: str = "master_time_control"


class BackupRunPayload(BaseModel):
    operator: str = "master"
    source: str = "master_api"
    trigger_type: str = "manual"


class ManualTimerPayload(BaseModel):
    operator: str = "master"
    source: str = "master_manual_timer"


class ContentImportPayload(BaseModel):
    manifest_path: str | None = None
    export_snapshot: bool = True


class SnapshotExportPayload(BaseModel):
    target_dir: str | None = None


class ReputationChangePayload(BaseModel):
    delta: int
    reason: str
    visibility: str = "player_and_master"
    source: str = "master_api"


class NpcEventPayload(BaseModel):
    seed_event_id: str | None = None
    npc_role: str | None = None
    event_type: str | None = None
    target_ids: list[str] | None = None
    price: dict[str, Any] | None = None
    condition: dict[str, Any] | None = None
    consequence: dict[str, Any] | None = None
    reputation_delta: int = 0
    visibility: str = "master_and_targets"
    severity: str | None = None
    final_flag: bool = False
    operator: str = "master"
    source: str = "master_api"


class NpcEventResolvePayload(BaseModel):
    operator: str = "master"
    reason: str
    status: str = "resolved"
    source: str = "master_api"


class SpellCastPayload(BaseModel):
    spell_id: str
    target_id: str
    target_type: str | None = None
    visibility: str = "player_and_master"
    cast_id: str | None = None
    source: str = "sorceress_api"


class PotionBuyPayload(BaseModel):
    potion_id: str
    quantity: int = 1
    source: str = "sorceress_api"


class PotionTransferPayload(BaseModel):
    to_player_id: str
    potion_id: str
    quantity: int = 1
    price_gold: int = 0
    mode: str = "gift"
    transfer_id: str | None = None
    auto_accept: bool = False
    source: str = "sorceress_api"


class PotionUsePayload(BaseModel):
    potion_id: str
    scene_id: str
    source: str = "mobile_api"


class MaterialMarketSellPayload(BaseModel):
    material_id: str
    quantity: int = 1
    sale_id: str | None = None
    source: str = "ios_player_app"


class TradeCreatePayload(BaseModel):
    from_player_id: str
    to_player_id: str
    asset_type: str
    asset_id: str
    quantity: int = 1
    price_gold: int = 0
    mode: str = "gift"
    transfer_id: str | None = None
    auto_accept: bool = False
    source: str = "trade_api"


class TradeAcceptPayload(BaseModel):
    accepted_by_player_id: str
    source: str = "trade_api"


class TradeDeclinePayload(BaseModel):
    declined_by_player_id: str
    reason: str = "declined"
    source: str = "trade_api"


class RewardApprovalPayload(BaseModel):
    action: str
    operator: str = "master"
    reason: str
    correction: dict[str, Any] | None = None
    source: str = "master_api"


class EventReviewPayload(BaseModel):
    action: str
    reason: str
    severity: str | None = None
    correction: dict[str, Any] | None = None
    operator: str = "master"
    source: str = "master_api"


class MasterCorrectionPayload(EventReviewPayload):
    event_id: str


class GameOpsCorrectionPayload(BaseModel):
    target_type: str
    target_id: str
    patch: dict[str, Any]
    operator: str
    reason: str
    source: str = "master_api"


class FavoriteCreatePayload(BaseModel):
    sorceress_id: str
    favored_player_id: str
    slot: str
    favorite_id: str | None = None
    passive_bonus_requested: bool = False
    source: str = "favorites_api"


class FavoriteAcceptPayload(BaseModel):
    accepted_by_player_id: str
    source: str = "favorites_api"


class AlignmentEvidencePayload(BaseModel):
    alignment_state: str
    evidence_type: str
    payload: dict[str, Any] | None = None
    visibility: str = "master_and_final_summary"
    final_flag: bool = False
    source: str = "sorceress_api"


class LordMovePayload(BaseModel):
    to_node_id: str | None = None
    route_node_ids: list[str] | None = None
    expected_cost: int | None = None
    source: str = "lord_panel"


class LordRoutePreviewPayload(BaseModel):
    to_node_id: str | None = None
    route_node_ids: list[str] | None = None
    source: str = "lord_panel"


class GarrisonTransferPayload(BaseModel):
    territory_id: str
    card_id: str | None = None
    stack_id: str | None = None
    target_stack_id: str | None = None
    army_id: str | None = None
    target_army_id: str | None = None
    garrison_id: str | None = None
    target_garrison_id: str | None = None
    count: int = 1
    operation: str = "garrison"
    source: str = "lord_panel"


class BuildingPurchasePayload(BaseModel):
    building_id: str
    territory_id: str | None = None
    source: str = "lord_panel"


class RecruitPayload(BaseModel):
    action: str
    offer_id: str | None = None
    card_id: str | None = None
    quantity: int = 1
    territory_id: str | None = None
    source: str = "lord_panel"


class RaidPayload(BaseModel):
    target_territory_id: str
    rule_id: str | None = None
    expected_token_cost: int | None = None
    expected_gold_cost: int | None = None
    source: str = "lord_panel"


class RaidCleansePayload(BaseModel):
    raid_effect_id: str
    source: str = "lord_panel"


class OrderPayload(BaseModel):
    action: str = "create"
    order_id: str | None = None
    object_id: str | None = None
    location_id: str | None = None
    target_player_id: str | None = None
    visibility: str = "public"
    escrow_reward_id: str | None = None
    visible_hook: str | None = None
    reward: str | dict[str, Any] | None = None
    expires_at: str | None = None
    player_id: str | None = None
    result_event_id: str | None = None
    reason: str | None = None
    source: str = "lord_panel"


class PvpChallengePayload(BaseModel):
    challenger_id: str
    target_id: str
    stake: dict[str, Any]
    challenge_id: str | None = None
    mandatory: bool = True
    master_approval: bool = False
    source: str = "pvp_api"


class PvpStartPayload(BaseModel):
    master_approval: bool = False
    mulligans_by_player: dict[str, list[str]] | None = None
    deck_ids_by_player: dict[str, str] | None = None
    preferred_starting_player_id: str | None = None
    source: str = "pvp_api"


class GwentPreparationPayload(BaseModel):
    mulligans: list[str] | None = None
    deck_id: str | None = None
    preferred_starting_player_id: str | None = None
    source: str = "ios_gwent_app"


class GwentRoundPayload(BaseModel):
    round_number: int | None = None
    round_state: dict[str, Any] | None = None
    plays: list[dict[str, Any]] | None = None
    passed: dict[str, bool] | None = None
    source: str = "pvp_api"


class GwentActionPayload(BaseModel):
    action: str
    round_number: int | None = None
    card_id: str | None = None
    row: str | None = None
    target_card_id: str | None = None
    discard_card_ids: list[str] | None = None
    revive_card_id: str | None = None
    revive_row: str | None = None
    action_id: str | None = None
    source: str = "pvp_api"


class GwentBotMatchPayload(BaseModel):
    mulligans: list[str] | None = None
    deck_id: str | None = None
    source: str = "ios_gwent_app"


class GwentDeckSavePayload(BaseModel):
    deck_id: str | None = None
    leader_card_id: str
    card_ids: list[str]
    source: str = "ios_gwent_app"


class GwentFinishPayload(BaseModel):
    winner_id: str | None = None
    outcome: str = "normal"
    source: str = "pvp_api"


class PvpRefusalPayload(BaseModel):
    reason: str
    actor_id: str | None = None
    source: str = "pvp_api"


class PvpThrottlePayload(BaseModel):
    mode: str
    operator: str = "master"
    source: str = "master_api"


class CardConversionPayload(BaseModel):
    player_id: str
    lord_id: str
    personal_card_id: str
    source: str = "pvp_api"


class LordBattleCreatePayload(BaseModel):
    battle_id: str | None = None
    attacker_domain_id: str | None = None
    attacker_lord_id: str | None = None
    defender_domain_id: str | None = None
    defender_lord_id: str | None = None
    territory_id: str | None = None
    claim_id: str | None = None
    seed: str | None = None
    source: str = "lord_battle_api"


class LordBattleActionPayload(BaseModel):
    action_type: str
    actor_side: str
    action_id: str | None = None
    actor_domain_id: str | None = None
    payload: dict[str, Any] | None = None
    source: str = "lord_battle_api"


class FinalMasterNotePayload(BaseModel):
    note_text: str
    category: str = "ruling"
    target_id: str | None = None
    visibility: str = "masters"
    operator: str = "master"
    source: str = "master_api"
    note_id: str | None = None


def create_app(settings: Settings | None = None):
    if FastAPI is None:
        raise RuntimeError(
            "FastAPI is not installed. Install backend dependencies with "
            "`uv sync` and run backend commands through `uv run python`."
        )

    runtime_settings = settings or Settings.from_env()
    init_database(runtime_settings)
    api = FastAPI(title=runtime_settings.app_name)
    api.add_middleware(
        CORSMiddleware,
        allow_origins=list(runtime_settings.cors_allow_origins),
        allow_methods=["*"],
        allow_headers=["*"],
    )
    api.mount("/static", StaticFiles(directory=WEB_ROOT), name="static")
    api.mount(
        "/assets",
        StaticFiles(directory=LORD_FRONTEND_ASSETS, check_dir=False),
        name="lord-assets",
    )
    from .event_models import EventSyncRequest, EventSyncResponse
    from .event_service import sync_events

    @api.get("/", include_in_schema=False)
    def index_redirect():
        return RedirectResponse(url="/admin")

    @api.get("/admin", include_in_schema=False)
    @api.get("/admin/", include_in_schema=False)
    def admin_studio():
        return FileResponse(ADMIN_STUDIO_INDEX)

    @api.get("/lords", include_in_schema=False)
    @api.get("/lords/{path:path}", include_in_schema=False)
    def lord_frontend(path: str = ""):
        if not LORD_FRONTEND_INDEX.exists():
            raise HTTPException(
                status_code=503,
                detail=(
                    "Lord frontend build is not available. Run "
                    "`uv run python scripts/build_lord_frontend.py` before starting production."
                ),
            )
        return FileResponse(LORD_FRONTEND_INDEX)

    @api.get("/health")
    def health() -> dict[str, object]:
        return {
            "status": "ok",
            "service": runtime_settings.app_name,
            "database": healthcheck_database(runtime_settings).as_dict(),
            "api": {
                "revision": API_REVISION,
                "features": list(API_FEATURES),
            },
        }

    @api.get("/api/content/snapshot")
    def content_snapshot(player_code: str | None = None):
        if not player_code or not player_code.strip():
            raise HTTPException(status_code=401, detail="Player code is required.")
        with connect(runtime_settings) as connection:
            if _authenticate_player_code(connection, player_code) is None:
                raise HTTPException(status_code=401, detail="Invalid player code.")
            snapshot = build_snapshot_from_database(connection, player_code=player_code)
        if snapshot is None:
            raise HTTPException(status_code=404, detail="No imported snapshot is available.")
        return snapshot

    @api.post("/api/qr/lookup")
    def qr_lookup(
        payload: QrLookupPayload,
        x_player_code: str | None = Header(default=None, alias="X-Player-Code"),
        player_code: str | None = None,
    ):
        if not payload.code.strip():
            raise HTTPException(status_code=400, detail="QR/manual ID is required.")
        with connect(runtime_settings) as connection:
            lookup_player_code = x_player_code or player_code
            if not lookup_player_code or not lookup_player_code.strip():
                raise HTTPException(status_code=401, detail="Player code is required.")
            auth = _authenticate_player_code(connection, lookup_player_code)
            if auth is None:
                raise HTTPException(status_code=401, detail="Invalid player code.")
            player_id = str(auth["player_id"])
            if payload.player_id and payload.player_id != player_id:
                raise HTTPException(
                    status_code=403,
                    detail="QR lookup player_id must match authenticated player.",
                )
            if not has_qr_content(connection):
                raise HTTPException(status_code=404, detail="No imported QR content is available.")
            return lookup_qr_runtime(
                connection,
                QrLookupRequest(
                    code=payload.code,
                    player_id=player_id,
                    device_id=payload.device_id,
                    source=payload.source,
                    physical_presence_confirmed=payload.physical_presence_confirmed,
                ),
            )

    @api.post("/api/mobile/qr-order-check")
    def mobile_qr_order_check(
        payload: QrOrderCheckPayload,
        x_player_code: str | None = Header(default=None, alias="X-Player-Code"),
        player_code: str | None = None,
    ):
        if not payload.code.strip():
            raise HTTPException(status_code=400, detail="QR/manual ID is required.")
        with connect(runtime_settings) as connection:
            lookup_player_code = x_player_code or player_code
            if not lookup_player_code or not lookup_player_code.strip():
                raise HTTPException(status_code=401, detail="Player code is required.")
            auth = _authenticate_player_code(connection, lookup_player_code)
            if auth is None:
                raise HTTPException(status_code=401, detail="Invalid player code.")
            if not has_qr_content(connection):
                raise HTTPException(status_code=404, detail="No imported QR content is available.")
            return _build_mobile_qr_order_check(
                connection,
                player_id=str(auth["player_id"]),
                code=payload.code,
                device_id=payload.device_id,
                source=payload.source,
            )

    @api.post("/api/events/sync", response_model=EventSyncResponse)
    def event_sync(
        request: EventSyncRequest,
        x_player_code: str | None = Header(default=None, alias="X-Player-Code"),
        x_role_token: str | None = Header(default=None, alias="X-Role-Token"),
        player_code: str | None = None,
        role_token: str | None = None,
    ) -> EventSyncResponse:
        with connect(runtime_settings) as connection:
            auth = _require_actor_context(
                connection,
                player_code=x_player_code or player_code,
                role_token=x_role_token or role_token,
            )
            trusted_request = request.model_copy(
                update={
                    "actor_id": auth["actor_id"],
                    "actor_type": auth["event_actor_type"],
                }
            )
            return sync_events(connection, trusted_request)

    @api.post("/api/auth/role-token")
    def role_token_auth(request: RoleTokenRequest):
        with connect(runtime_settings) as connection:
            auth = _authenticate_role_token_or_lord_code(connection, request.token)
        if auth is None:
            raise HTTPException(status_code=401, detail="Invalid role token.")
        return auth.model_dump()

    @api.post("/api/auth/player-code")
    def player_code_auth(request: PlayerCodePayload):
        if not request.player_code.strip():
            raise HTTPException(status_code=400, detail="Player code is required.")
        with connect(runtime_settings) as connection:
            auth = _authenticate_player_code(connection, request.player_code)
        if auth is None:
            raise HTTPException(status_code=401, detail="Invalid player code.")
        return {
            **auth,
            "device_id": request.device_id,
            "snapshot_path": "/api/content/snapshot",
        }

    @api.get("/api/master/admin/overview")
    def master_admin_overview(
        x_role_token: str | None = Header(default=None, alias="X-Role-Token"),
        role_token: str | None = None,
    ):
        with connect(runtime_settings) as connection:
            _require_master_token(connection, x_role_token or role_token)
            return build_admin_overview(connection)

    @api.get("/api/master/content/packs")
    def master_content_packs(
        x_role_token: str | None = Header(default=None, alias="X-Role-Token"),
        role_token: str | None = None,
    ):
        with connect(runtime_settings) as connection:
            _require_master_token(connection, x_role_token or role_token)
        return list_content_packs()

    @api.get("/api/master/content/import-report/latest")
    def master_latest_import_report(
        x_role_token: str | None = Header(default=None, alias="X-Role-Token"),
        role_token: str | None = None,
    ):
        with connect(runtime_settings) as connection:
            _require_master_token(connection, x_role_token or role_token)
            return latest_import_report(connection)

    @api.post("/api/master/content/import")
    def master_content_import(
        payload: ContentImportPayload,
        x_role_token: str | None = Header(default=None, alias="X-Role-Token"),
        role_token: str | None = None,
    ):
        with connect(runtime_settings) as connection:
            _require_master_token(connection, x_role_token or role_token)
        try:
            manifest_path = resolve_manifest_path(payload.manifest_path)
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(
                status_code=400,
                detail={"code": "content_path", "message": str(exc)},
            ) from exc
        report = import_seed_pack(
            runtime_settings,
            manifest_path=manifest_path,
            snapshot_dir=DEFAULT_SNAPSHOT_DIR if payload.export_snapshot else None,
        )
        return {
            **report.as_dict(),
            "error_count": len(report.errors),
        }

    @api.post("/api/master/content/snapshot/export")
    def master_snapshot_export(
        payload: SnapshotExportPayload,
        x_role_token: str | None = Header(default=None, alias="X-Role-Token"),
        role_token: str | None = None,
    ):
        try:
            snapshot_dir = resolve_snapshot_dir(payload.target_dir, DEFAULT_SNAPSHOT_DIR)
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail={"code": "content_path", "message": str(exc)},
            ) from exc
        with connect(runtime_settings) as connection:
            _require_master_token(connection, x_role_token or role_token)
            result = export_latest_snapshot(connection, snapshot_dir)
        if result["status"] != "success":
            raise HTTPException(status_code=404, detail="No imported snapshot is available.")
        return result

    @api.get("/api/master/content/qr-checklist")
    def master_qr_checklist(
        x_role_token: str | None = Header(default=None, alias="X-Role-Token"),
        role_token: str | None = None,
    ):
        with connect(runtime_settings) as connection:
            _require_master_token(connection, x_role_token or role_token)
            return build_qr_checklist(connection)

    @api.get("/api/master/content/handout-checklist")
    def master_handout_checklist(
        x_role_token: str | None = Header(default=None, alias="X-Role-Token"),
        role_token: str | None = None,
    ):
        with connect(runtime_settings) as connection:
            _require_master_token(connection, x_role_token or role_token)
            return build_handout_checklist(connection)

    @api.get("/api/master/state")
    def master_state(
        x_role_token: str | None = Header(default=None, alias="X-Role-Token"),
        role_token: str | None = None,
    ):
        with connect(runtime_settings) as connection:
            _require_master_token(connection, x_role_token or role_token)
            return build_master_state(connection, runtime_settings)

    @api.get("/api/master/player-codes")
    def master_player_codes(
        request: Request,
        x_role_token: str | None = Header(default=None, alias="X-Role-Token"),
        role_token: str | None = None,
    ):
        with connect(runtime_settings) as connection:
            _require_master_token(connection, x_role_token or role_token)
            payload = list_master_player_codes(connection)
        return {
            **payload,
            "server_url": _suggested_lan_server_url(request),
            "player_login_url": _suggested_player_login_url(request),
        }

    @api.post("/api/master/game/start-setup")
    def master_game_start_setup(
        payload: GameStartSetupPayload,
        x_role_token: str | None = Header(default=None, alias="X-Role-Token"),
        role_token: str | None = None,
    ):
        with connect(runtime_settings) as connection:
            _require_master_token(connection, x_role_token or role_token)
            ensure_lord_runtime_state(connection)
            ensure_sorceress_runtime_state(connection)
            ensure_material_market_runtime_state(connection)
            act_state = get_act_state(connection, runtime_settings)
            current_act_id = act_state["state"].get("current_act_id")
            start_result = None
            elapsed_result = None
            try:
                start_result = start_act(
                    connection,
                    runtime_settings,
                    payload.act_id,
                    operator=payload.operator,
                    source=payload.source,
                    physical_announcement_state=payload.physical_announcement_state,
                )
            except ActNotFoundError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc

            if current_act_id == payload.act_id:
                elapsed_result = set_active_act_elapsed_minutes(
                    connection,
                    runtime_settings,
                    0,
                    operator=payload.operator,
                    source=payload.source,
                )
                status = "restarted"
            elif current_act_id:
                status = "switched"
            else:
                status = "started"
            return {
                "status": status,
                "start_result": start_result,
                "elapsed_result": elapsed_result,
                "master_state": build_master_state(connection, runtime_settings),
            }

    @api.get("/api/master/visibility-audit")
    def master_visibility_audit(
        x_role_token: str | None = Header(default=None, alias="X-Role-Token"),
        role_token: str | None = None,
    ):
        with connect(runtime_settings) as connection:
            _require_master_token(connection, x_role_token or role_token)
            return build_visibility_audit(connection)

    @api.get("/api/master/backups/status")
    def master_backup_status(
        x_role_token: str | None = Header(default=None, alias="X-Role-Token"),
        role_token: str | None = None,
    ):
        with connect(runtime_settings) as connection:
            _require_master_token(connection, x_role_token or role_token)
            return backup_status(connection)

    @api.post("/api/master/game-ops/corrections")
    def master_game_ops_correction(
        payload: GameOpsCorrectionPayload,
        x_role_token: str | None = Header(default=None, alias="X-Role-Token"),
        role_token: str | None = None,
    ):
        with connect(runtime_settings) as connection:
            _require_master_token(connection, x_role_token or role_token)
            try:
                return apply_game_ops_correction(
                    connection,
                    target_type=payload.target_type,
                    target_id=payload.target_id,
                    patch=payload.patch,
                    operator=payload.operator,
                    reason=payload.reason,
                    source=payload.source,
                )
            except GameOpsCorrectionError as exc:
                raise _game_ops_http_error(exc) from exc

    @api.get("/api/lords/{lord_id}/state")
    def lord_state(
        lord_id: str,
        x_role_token: str | None = Header(default=None, alias="X-Role-Token"),
        role_token: str | None = None,
    ):
        token = x_role_token or role_token
        if not token:
            raise HTTPException(status_code=401, detail="Role token is required.")

        with connect(runtime_settings) as connection:
            _require_lord_token(connection, lord_id, token)
            _reconcile_due_timers(connection, runtime_settings)
            state = build_lord_state(connection, lord_id)

        if state is None:
            raise HTTPException(status_code=404, detail="Lord state is not available.")
        return state

    @api.get("/api/lords/{lord_id}/summary")
    def lord_summary(
        lord_id: str,
        x_role_token: str | None = Header(default=None, alias="X-Role-Token"),
        role_token: str | None = None,
    ):
        token = x_role_token or role_token
        if not token:
            raise HTTPException(status_code=401, detail="Role token is required.")

        with connect(runtime_settings) as connection:
            _require_lord_token(connection, lord_id, token)
            _reconcile_due_timers(connection, runtime_settings)
            state = build_lord_summary_state(connection, lord_id)

        if state is None:
            raise HTTPException(status_code=404, detail="Lord summary is not available.")
        return state

    @api.post("/api/lords/{lord_id}/move")
    def lord_move(
        lord_id: str,
        payload: LordMovePayload,
        x_role_token: str | None = Header(default=None, alias="X-Role-Token"),
        role_token: str | None = None,
    ):
        with connect(runtime_settings) as connection:
            _require_lord_token(connection, lord_id, x_role_token or role_token)
            _reconcile_due_timers(connection, runtime_settings)
            try:
                return move_lord(
                    connection,
                    lord_id,
                    to_node_id=payload.to_node_id,
                    route_node_ids=payload.route_node_ids,
                    expected_cost=payload.expected_cost,
                    source=payload.source,
                )
            except LordRuntimeError as exc:
                raise _lord_http_error(exc) from exc

    @api.post("/api/lords/{lord_id}/route-preview")
    def lord_route_preview(
        lord_id: str,
        payload: LordRoutePreviewPayload,
        x_role_token: str | None = Header(default=None, alias="X-Role-Token"),
        role_token: str | None = None,
    ):
        with connect(runtime_settings) as connection:
            _require_lord_token(connection, lord_id, x_role_token or role_token)
            _reconcile_due_timers(connection, runtime_settings)
            try:
                return preview_lord_route(
                    connection,
                    lord_id,
                    to_node_id=payload.to_node_id,
                    route_node_ids=payload.route_node_ids,
                    source=payload.source,
                )
            except LordRuntimeError as exc:
                raise _lord_http_error(exc) from exc

    @api.post("/api/lords/{lord_id}/garrisons/transfer")
    def lord_garrison_transfer(
        lord_id: str,
        payload: GarrisonTransferPayload,
        x_role_token: str | None = Header(default=None, alias="X-Role-Token"),
        role_token: str | None = None,
    ):
        with connect(runtime_settings) as connection:
            _require_lord_token(connection, lord_id, x_role_token or role_token)
            _reconcile_due_timers(connection, runtime_settings)
            try:
                return transfer_garrison(
                    connection,
                    lord_id,
                    territory_id=payload.territory_id,
                    card_id=payload.card_id,
                    stack_id=payload.stack_id,
                    target_stack_id=payload.target_stack_id,
                    army_id=payload.army_id,
                    target_army_id=payload.target_army_id,
                    garrison_id=payload.garrison_id,
                    target_garrison_id=payload.target_garrison_id,
                    count=payload.count,
                    operation=payload.operation,
                    source=payload.source,
                )
            except LordRuntimeError as exc:
                raise _lord_http_error(exc) from exc

    @api.post("/api/lords/{lord_id}/buildings")
    def lord_buy_building(
        lord_id: str,
        payload: BuildingPurchasePayload,
        x_role_token: str | None = Header(default=None, alias="X-Role-Token"),
        role_token: str | None = None,
    ):
        with connect(runtime_settings) as connection:
            _require_lord_token(connection, lord_id, x_role_token or role_token)
            _reconcile_due_timers(connection, runtime_settings)
            try:
                return buy_building(
                    connection,
                    lord_id,
                    building_id=payload.building_id,
                    territory_id=payload.territory_id,
                    source=payload.source,
                )
            except LordRuntimeError as exc:
                raise _lord_http_error(exc) from exc

    @api.post("/api/lords/{lord_id}/recruit")
    def lord_recruit(
        lord_id: str,
        payload: RecruitPayload,
        x_role_token: str | None = Header(default=None, alias="X-Role-Token"),
        role_token: str | None = None,
    ):
        with connect(runtime_settings) as connection:
            _require_lord_token(connection, lord_id, x_role_token or role_token)
            _reconcile_due_timers(connection, runtime_settings)
            try:
                return recruit_action(
                    connection,
                    lord_id,
                    action=payload.action,
                    offer_id=payload.offer_id,
                    card_id=payload.card_id,
                    quantity=payload.quantity,
                    territory_id=payload.territory_id,
                    source=payload.source,
                )
            except LordRuntimeError as exc:
                raise _lord_http_error(exc) from exc

    @api.post("/api/lords/{lord_id}/raids")
    def lord_raid(
        lord_id: str,
        payload: RaidPayload,
        x_role_token: str | None = Header(default=None, alias="X-Role-Token"),
        role_token: str | None = None,
    ):
        with connect(runtime_settings) as connection:
            _require_lord_token(connection, lord_id, x_role_token or role_token)
            _reconcile_due_timers(connection, runtime_settings)
            try:
                return start_raid(
                    connection,
                    lord_id,
                    target_territory_id=payload.target_territory_id,
                    rule_id=payload.rule_id,
                    expected_token_cost=payload.expected_token_cost,
                    expected_gold_cost=payload.expected_gold_cost,
                    source=payload.source,
                )
            except LordRuntimeError as exc:
                raise _lord_http_error(exc) from exc

    @api.post("/api/lords/{lord_id}/raids/cleanse")
    def lord_raid_cleanse(
        lord_id: str,
        payload: RaidCleansePayload,
        x_role_token: str | None = Header(default=None, alias="X-Role-Token"),
        role_token: str | None = None,
    ):
        with connect(runtime_settings) as connection:
            _require_lord_token(connection, lord_id, x_role_token or role_token)
            _reconcile_due_timers(connection, runtime_settings)
            try:
                return cleanse_raid_effect(
                    connection,
                    lord_id,
                    raid_effect_id=payload.raid_effect_id,
                    source=payload.source,
                )
            except LordRuntimeError as exc:
                raise _lord_http_error(exc) from exc

    @api.post("/api/lords/{lord_id}/orders")
    def lord_order(
        lord_id: str,
        payload: OrderPayload,
        x_player_code: str | None = Header(default=None, alias="X-Player-Code"),
        x_role_token: str | None = Header(default=None, alias="X-Role-Token"),
        player_code: str | None = None,
        role_token: str | None = None,
    ):
        with connect(runtime_settings) as connection:
            token = x_role_token or role_token
            player_id = payload.player_id
            actor_role = "lord"
            source = payload.source
            if payload.action in {"accept", "submit_success"}:
                auth = _require_actor_context(
                    connection,
                    player_code=x_player_code or player_code,
                    role_token=token,
                )
                if auth["is_master"]:
                    actor_role = "master"
                    source = "master_api" if payload.source == "lord_panel" else payload.source
                else:
                    if auth["scope"] != "player_code":
                        raise HTTPException(
                            status_code=403,
                            detail="Order player actions require player code auth.",
                        )
                    if payload.player_id and payload.player_id != auth["player_id"]:
                        raise HTTPException(
                            status_code=403,
                            detail="Authenticated player cannot act for another order executor.",
                        )
                    actor_role = "player"
                    player_id = auth["player_id"]
                    source = "player_app" if payload.source == "lord_panel" else payload.source
            elif payload.action == "complete":
                _require_master_token(connection, token)
                actor_role = "master"
                source = "master_api" if payload.source == "lord_panel" else payload.source
            else:
                _require_lord_token(connection, lord_id, token)
            _reconcile_due_timers(connection, runtime_settings)
            try:
                result = order_action(
                    connection,
                    lord_id,
                    action=payload.action,
                    order_id=payload.order_id,
                    object_id=payload.object_id or payload.location_id,
                    target_player_id=payload.target_player_id,
                    visibility=payload.visibility,
                    escrow_reward_id=payload.escrow_reward_id
                    or _order_reward_id(connection, payload.reward),
                    visible_hook=payload.visible_hook,
                    expires_at=payload.expires_at,
                    player_id=player_id,
                    result_event_id=payload.result_event_id,
                    reason=payload.reason,
                    source=source,
                    actor_role=actor_role,
                )
                if payload.action in {"create", "cancel"}:
                    return _with_lord_order_state(connection, lord_id, result)
                return result
            except LordRuntimeError as exc:
                raise _lord_http_error(exc) from exc

    @api.get("/api/master/acts/state")
    def master_act_state(
        x_role_token: str | None = Header(default=None, alias="X-Role-Token"),
        role_token: str | None = None,
    ):
        with connect(runtime_settings) as connection:
            _require_master_token(connection, x_role_token or role_token)
            return get_act_state(connection, runtime_settings)

    @api.post("/api/master/acts/{act_id}/start")
    def master_start_act(
        act_id: str,
        payload: ActStartPayload,
        x_role_token: str | None = Header(default=None, alias="X-Role-Token"),
        role_token: str | None = None,
    ):
        with connect(runtime_settings) as connection:
            _require_master_token(connection, x_role_token or role_token)
            try:
                return start_act(
                    connection,
                    runtime_settings,
                    act_id,
                    operator=payload.operator,
                    source=payload.source,
                    physical_announcement_state=payload.physical_announcement_state,
                )
            except ActNotFoundError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc

    @api.post("/api/master/acts/{act_id}/physical-announcement")
    def master_record_physical_announcement(
        act_id: str,
        payload: PhysicalAnnouncementPayload,
        x_role_token: str | None = Header(default=None, alias="X-Role-Token"),
        role_token: str | None = None,
    ):
        with connect(runtime_settings) as connection:
            _require_master_token(connection, x_role_token or role_token)
            try:
                return record_physical_announcement(
                    connection,
                    act_id,
                    operator=payload.operator,
                    source=payload.source,
                    state=payload.state,
                )
            except UnlockCodeHiddenError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc

    @api.post("/api/master/acts/elapsed")
    def master_set_act_elapsed(
        payload: ActElapsedPayload,
        x_role_token: str | None = Header(default=None, alias="X-Role-Token"),
        role_token: str | None = None,
    ):
        with connect(runtime_settings) as connection:
            _require_master_token(connection, x_role_token or role_token)
            try:
                return set_active_act_elapsed_minutes(
                    connection,
                    runtime_settings,
                    payload.elapsed_minutes,
                    operator=payload.operator,
                    source=payload.source,
                )
            except UnlockCodeHiddenError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc

    @api.get("/api/master/acts/{act_id}/unlock-code")
    def master_unlock_code(
        act_id: str,
        operator: str = "master",
        x_role_token: str | None = Header(default=None, alias="X-Role-Token"),
        role_token: str | None = None,
    ):
        with connect(runtime_settings) as connection:
            _require_master_token(connection, x_role_token or role_token)
            try:
                return reveal_unlock_code(connection, act_id, operator=operator)
            except ActNotFoundError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            except UnlockCodeHiddenError as exc:
                raise HTTPException(status_code=403, detail=str(exc)) from exc

    @api.get("/api/master/timers")
    def master_timers(
        x_role_token: str | None = Header(default=None, alias="X-Role-Token"),
        role_token: str | None = None,
    ):
        with connect(runtime_settings) as connection:
            _require_master_token(connection, x_role_token or role_token)
            applied = apply_due_timers(connection, runtime_settings)
            status = timer_status(connection)
        return {**status, "applied_now": applied}

    @api.post("/api/master/timers/lord-income-tick")
    def master_lord_income_tick(
        payload: ManualTimerPayload,
        x_role_token: str | None = Header(default=None, alias="X-Role-Token"),
        role_token: str | None = None,
    ):
        with connect(runtime_settings) as connection:
            _require_master_token(connection, x_role_token or role_token)
            tick = apply_manual_lord_income_tick(
                connection,
                operator=payload.operator,
                source=payload.source,
            )
            status = timer_status(connection)
        return {**status, "applied_now": [tick]}

    @api.post("/api/backups/run")
    def backup_run(
        payload: BackupRunPayload,
        x_role_token: str | None = Header(default=None, alias="X-Role-Token"),
        role_token: str | None = None,
    ):
        with connect(runtime_settings) as connection:
            _require_master_token(connection, x_role_token or role_token)
            result = run_backup(
                connection,
                runtime_settings,
                trigger_type=payload.trigger_type,
                operator=payload.operator,
                source=payload.source,
            )
            return result.as_dict()

    @api.get("/api/players/{player_id}/reputation")
    def player_reputation(
        player_id: str,
        x_player_code: str | None = Header(default=None, alias="X-Player-Code"),
        x_role_token: str | None = Header(default=None, alias="X-Role-Token"),
        player_code: str | None = None,
        role_token: str | None = None,
    ):
        with connect(runtime_settings) as connection:
            auth = _require_player_or_master(
                connection,
                player_id=player_id,
                player_code=x_player_code or player_code,
                role_token=x_role_token or role_token,
            )
            try:
                visibility = "master" if auth["is_master"] else "player"
                return get_reputation_view(connection, player_id, visibility=visibility)
            except ReputationError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

    @api.get("/api/master/reputation/{player_id}")
    def master_reputation(
        player_id: str,
        x_role_token: str | None = Header(default=None, alias="X-Role-Token"),
        role_token: str | None = None,
    ):
        with connect(runtime_settings) as connection:
            _require_master_token(connection, x_role_token or role_token)
            try:
                return get_reputation_view(connection, player_id, visibility="master")
            except ReputationError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

    @api.post("/api/master/reputation/{player_id}/change")
    def master_change_reputation(
        player_id: str,
        payload: ReputationChangePayload,
        x_role_token: str | None = Header(default=None, alias="X-Role-Token"),
        role_token: str | None = None,
    ):
        with connect(runtime_settings) as connection:
            _require_master_token(connection, x_role_token or role_token)
            try:
                change = apply_reputation_change(
                    connection,
                    player_id,
                    payload.delta,
                    reason=payload.reason,
                    visibility=payload.visibility,
                    source=payload.source,
                )
                view = get_reputation_view(connection, player_id, visibility="master")
                return {"change": change, "reputation": view}
            except ReputationError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

    @api.post("/api/master/npc/events")
    def master_record_npc_event(
        payload: NpcEventPayload,
        x_role_token: str | None = Header(default=None, alias="X-Role-Token"),
        role_token: str | None = None,
    ):
        with connect(runtime_settings) as connection:
            _require_master_token(connection, x_role_token or role_token)
            try:
                return record_npc_event(
                    connection,
                    NpcEventInput(
                        seed_event_id=payload.seed_event_id,
                        npc_role=payload.npc_role,
                        event_type=payload.event_type,
                        target_ids=payload.target_ids,
                        price=payload.price,
                        condition=payload.condition,
                        consequence=payload.consequence,
                        reputation_delta=payload.reputation_delta,
                        visibility=payload.visibility,
                        severity=payload.severity,
                        final_flag=payload.final_flag,
                        operator=payload.operator,
                        source=payload.source,
                    ),
                )
            except (NpcEventError, ReputationError) as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

    @api.post("/api/master/npc/events/{npc_runtime_event_id}/resolve")
    def master_resolve_npc_event(
        npc_runtime_event_id: int,
        payload: NpcEventResolvePayload,
        x_role_token: str | None = Header(default=None, alias="X-Role-Token"),
        role_token: str | None = None,
    ):
        with connect(runtime_settings) as connection:
            _require_master_token(connection, x_role_token or role_token)
            try:
                return resolve_npc_event(
                    connection,
                    npc_runtime_event_id,
                    operator=payload.operator,
                    reason=payload.reason,
                    status=payload.status,
                    source=payload.source,
                )
            except NpcEventError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

    @api.get("/api/master/npc/events")
    def master_npc_events(
        x_role_token: str | None = Header(default=None, alias="X-Role-Token"),
        role_token: str | None = None,
    ):
        with connect(runtime_settings) as connection:
            _require_master_token(connection, x_role_token or role_token)
            return {"items": list_npc_events(connection, visibility="master")}

    @api.get("/api/master/npc/deals")
    def master_npc_deals(
        x_role_token: str | None = Header(default=None, alias="X-Role-Token"),
        role_token: str | None = None,
    ):
        with connect(runtime_settings) as connection:
            _require_master_token(connection, x_role_token or role_token)
            return {"items": list_npc_deals(connection, visibility="master")}

    @api.get("/api/master/review-queue")
    def master_review_queue(
        x_role_token: str | None = Header(default=None, alias="X-Role-Token"),
        role_token: str | None = None,
    ):
        with connect(runtime_settings) as connection:
            _require_master_token(connection, x_role_token or role_token)
            return review_queue(connection)

    @api.post("/api/events/{event_id}/review")
    def master_review_event(
        event_id: str,
        payload: EventReviewPayload,
        x_role_token: str | None = Header(default=None, alias="X-Role-Token"),
        role_token: str | None = None,
    ):
        with connect(runtime_settings) as connection:
            _require_master_token(connection, x_role_token or role_token)
            try:
                return decide_event_review(
                    connection,
                    event_id,
                    action=payload.action,
                    operator=payload.operator,
                    reason=payload.reason,
                    severity=payload.severity,
                    correction=payload.correction,
                    source=payload.source,
                )
            except ReviewDecisionError as exc:
                raise HTTPException(
                    status_code=exc.status_code,
                    detail={"code": exc.code, "message": exc.message},
                ) from exc

    @api.post("/api/master/corrections")
    def master_correction(
        payload: MasterCorrectionPayload,
        x_role_token: str | None = Header(default=None, alias="X-Role-Token"),
        role_token: str | None = None,
    ):
        with connect(runtime_settings) as connection:
            _require_master_token(connection, x_role_token or role_token)
            try:
                return decide_event_review(
                    connection,
                    payload.event_id,
                    action=payload.action,
                    operator=payload.operator,
                    reason=payload.reason,
                    severity=payload.severity,
                    correction=payload.correction,
                    source=payload.source,
                )
            except ReviewDecisionError as exc:
                raise HTTPException(
                    status_code=exc.status_code,
                    detail={"code": exc.code, "message": exc.message},
                ) from exc

    @api.post("/api/master/reward-approvals/{approval_id}")
    def master_reward_approval(
        approval_id: str,
        payload: RewardApprovalPayload,
        x_role_token: str | None = Header(default=None, alias="X-Role-Token"),
        role_token: str | None = None,
    ):
        with connect(runtime_settings) as connection:
            _require_master_token(connection, x_role_token or role_token)
            try:
                return decide_reward_approval(
                    connection,
                    approval_id=approval_id,
                    action=payload.action,
                    operator=payload.operator,
                    reason=payload.reason,
                    correction=payload.correction,
                    source=payload.source,
                )
            except AssetContractError as exc:
                raise _asset_http_error(exc) from exc

    @api.get("/api/master/final-summary")
    def master_final_summary(
        x_role_token: str | None = Header(default=None, alias="X-Role-Token"),
        role_token: str | None = None,
    ):
        with connect(runtime_settings) as connection:
            _require_master_token(connection, x_role_token or role_token)
            _reconcile_due_timers(connection, runtime_settings)
            return build_final_summary(connection)

    @api.post("/api/master/final-summary/notes")
    def master_final_summary_note(
        payload: FinalMasterNotePayload,
        x_role_token: str | None = Header(default=None, alias="X-Role-Token"),
        role_token: str | None = None,
    ):
        with connect(runtime_settings) as connection:
            _require_master_token(connection, x_role_token or role_token)
            try:
                return record_final_master_note(
                    connection,
                    note_id=payload.note_id,
                    category=payload.category,
                    target_id=payload.target_id,
                    note_text=payload.note_text,
                    visibility=payload.visibility,
                    operator=payload.operator,
                    source=payload.source,
                )
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

    @api.get("/api/sorceresses/{sorceress_id}/state")
    def sorceress_state(
        sorceress_id: str,
        x_player_code: str | None = Header(default=None, alias="X-Player-Code"),
        x_role_token: str | None = Header(default=None, alias="X-Role-Token"),
        player_code: str | None = None,
        role_token: str | None = None,
    ):
        with connect(runtime_settings) as connection:
            _require_player_or_master(
                connection,
                player_id=sorceress_id,
                allowed_roles={"sorceress"},
                player_code=x_player_code or player_code,
                role_token=x_role_token or role_token,
            )
            _reconcile_due_timers(connection, runtime_settings)
            try:
                return get_sorceress_state(connection, sorceress_id)
            except SorceressError as exc:
                raise _sorceress_http_error(exc) from exc

    @api.post("/api/sorceresses/{sorceress_id}/spells/cast")
    def sorceress_cast_spell(
        sorceress_id: str,
        payload: SpellCastPayload,
        x_player_code: str | None = Header(default=None, alias="X-Player-Code"),
        x_role_token: str | None = Header(default=None, alias="X-Role-Token"),
        player_code: str | None = None,
        role_token: str | None = None,
    ):
        with connect(runtime_settings) as connection:
            _require_player_or_master(
                connection,
                player_id=sorceress_id,
                allowed_roles={"sorceress"},
                player_code=x_player_code or player_code,
                role_token=x_role_token or role_token,
            )
            _reconcile_due_timers(connection, runtime_settings)
            try:
                return cast_spell(
                    connection,
                    sorceress_id=sorceress_id,
                    spell_id=payload.spell_id,
                    target_type=payload.target_type,
                    target_id=payload.target_id,
                    visibility=payload.visibility,
                    cast_id=payload.cast_id,
                    source=payload.source,
                )
            except SorceressError as exc:
                raise _sorceress_http_error(exc) from exc

    @api.post("/api/sorceresses/{sorceress_id}/potions/buy")
    def sorceress_buy_potion(
        sorceress_id: str,
        payload: PotionBuyPayload,
        x_player_code: str | None = Header(default=None, alias="X-Player-Code"),
        x_role_token: str | None = Header(default=None, alias="X-Role-Token"),
        player_code: str | None = None,
        role_token: str | None = None,
    ):
        with connect(runtime_settings) as connection:
            _require_player_or_master(
                connection,
                player_id=sorceress_id,
                allowed_roles={"sorceress"},
                player_code=x_player_code or player_code,
                role_token=x_role_token or role_token,
            )
            _reconcile_due_timers(connection, runtime_settings)
            try:
                return buy_potion(
                    connection,
                    buyer_id=sorceress_id,
                    potion_id=payload.potion_id,
                    quantity=payload.quantity,
                    source=payload.source,
                )
            except SorceressError as exc:
                raise _sorceress_http_error(exc) from exc

    @api.post("/api/sorceresses/{sorceress_id}/potions/transfer")
    def sorceress_transfer_potion(
        sorceress_id: str,
        payload: PotionTransferPayload,
        x_player_code: str | None = Header(default=None, alias="X-Player-Code"),
        x_role_token: str | None = Header(default=None, alias="X-Role-Token"),
        player_code: str | None = None,
        role_token: str | None = None,
    ):
        with connect(runtime_settings) as connection:
            auth = _require_player_or_master(
                connection,
                player_id=sorceress_id,
                allowed_roles={"sorceress"},
                player_code=x_player_code or player_code,
                role_token=x_role_token or role_token,
            )
            if payload.auto_accept and not auth["is_master"] and auth["player_id"] != payload.to_player_id:
                raise HTTPException(status_code=403, detail="Auto-accept requires target player or master auth.")
            _reconcile_due_timers(connection, runtime_settings)
            try:
                return transfer_potion(
                    connection,
                    from_player_id=sorceress_id,
                    to_player_id=payload.to_player_id,
                    potion_id=payload.potion_id,
                    quantity=payload.quantity,
                    price_gold=payload.price_gold,
                    mode=payload.mode,
                    transfer_id=payload.transfer_id,
                    auto_accept=payload.auto_accept,
                    source=payload.source,
                )
            except SorceressError as exc:
                raise _sorceress_http_error(exc) from exc

    @api.post("/api/players/{player_id}/potions/use")
    def player_use_potion(
        player_id: str,
        payload: PotionUsePayload,
        x_player_code: str | None = Header(default=None, alias="X-Player-Code"),
        x_role_token: str | None = Header(default=None, alias="X-Role-Token"),
        player_code: str | None = None,
        role_token: str | None = None,
    ):
        with connect(runtime_settings) as connection:
            _require_player_or_master(
                connection,
                player_id=player_id,
                player_code=x_player_code or player_code,
                role_token=x_role_token or role_token,
            )
            _reconcile_due_timers(connection, runtime_settings)
            try:
                return use_potion_in_scene(
                    connection,
                    player_id=player_id,
                    potion_id=payload.potion_id,
                    scene_id=payload.scene_id,
                    source=payload.source,
                )
            except SorceressError as exc:
                raise _sorceress_http_error(exc) from exc

    @api.post("/api/players/{player_id}/material-market/sell")
    def player_sell_material_to_market(
        player_id: str,
        payload: MaterialMarketSellPayload,
        x_player_code: str | None = Header(default=None, alias="X-Player-Code"),
        x_role_token: str | None = Header(default=None, alias="X-Role-Token"),
        player_code: str | None = None,
        role_token: str | None = None,
    ):
        with connect(runtime_settings) as connection:
            _require_player_or_master(
                connection,
                player_id=player_id,
                player_code=x_player_code or player_code,
                role_token=x_role_token or role_token,
            )
            _reconcile_due_timers(connection, runtime_settings)
            try:
                return sell_material_to_market(
                    connection,
                    player_id=player_id,
                    material_id=payload.material_id,
                    quantity=payload.quantity,
                    sale_id=payload.sale_id,
                    source=payload.source,
                )
            except MaterialMarketError as exc:
                raise _material_market_http_error(exc) from exc

    @api.post("/api/trade-transfers")
    def trade_transfer_create(
        payload: TradeCreatePayload,
        x_player_code: str | None = Header(default=None, alias="X-Player-Code"),
        x_role_token: str | None = Header(default=None, alias="X-Role-Token"),
        player_code: str | None = None,
        role_token: str | None = None,
    ):
        with connect(runtime_settings) as connection:
            auth = _require_player_or_master(
                connection,
                player_id=payload.from_player_id,
                player_code=x_player_code or player_code,
                role_token=x_role_token or role_token,
            )
            if payload.auto_accept and not auth["is_master"] and auth["player_id"] != payload.to_player_id:
                raise HTTPException(status_code=403, detail="Auto-accept requires target player or master auth.")
            _reconcile_due_timers(connection, runtime_settings)
            try:
                return create_trade_transfer(
                    connection,
                    from_player_id=payload.from_player_id,
                    to_player_id=payload.to_player_id,
                    asset_type=payload.asset_type,
                    asset_id=payload.asset_id,
                    quantity=payload.quantity,
                    price_gold=payload.price_gold,
                    mode=payload.mode,
                    transfer_id=payload.transfer_id,
                    auto_accept=payload.auto_accept,
                    source=payload.source,
                )
            except SorceressError as exc:
                raise _sorceress_http_error(exc) from exc

    @api.post("/api/trade-transfers/{transfer_id}/accept")
    def trade_transfer_accept(
        transfer_id: str,
        payload: TradeAcceptPayload,
        x_player_code: str | None = Header(default=None, alias="X-Player-Code"),
        x_role_token: str | None = Header(default=None, alias="X-Role-Token"),
        player_code: str | None = None,
        role_token: str | None = None,
    ):
        with connect(runtime_settings) as connection:
            _require_player_or_master(
                connection,
                player_id=payload.accepted_by_player_id,
                player_code=x_player_code or player_code,
                role_token=x_role_token or role_token,
            )
            _reconcile_due_timers(connection, runtime_settings)
            try:
                return accept_trade_transfer(
                    connection,
                    transfer_id,
                    accepted_by_player_id=payload.accepted_by_player_id,
                    source=payload.source,
                )
            except SorceressError as exc:
                raise _sorceress_http_error(exc) from exc

    @api.post("/api/trade-transfers/{transfer_id}/decline")
    def trade_transfer_decline(
        transfer_id: str,
        payload: TradeDeclinePayload,
        x_player_code: str | None = Header(default=None, alias="X-Player-Code"),
        x_role_token: str | None = Header(default=None, alias="X-Role-Token"),
        player_code: str | None = None,
        role_token: str | None = None,
    ):
        with connect(runtime_settings) as connection:
            _require_player_or_master(
                connection,
                player_id=payload.declined_by_player_id,
                player_code=x_player_code or player_code,
                role_token=x_role_token or role_token,
            )
            _reconcile_due_timers(connection, runtime_settings)
            try:
                return decline_trade_transfer(
                    connection,
                    transfer_id,
                    declined_by_player_id=payload.declined_by_player_id,
                    reason=payload.reason,
                    source=payload.source,
                )
            except SorceressError as exc:
                raise _sorceress_http_error(exc) from exc

    @api.post("/api/favorites")
    def favorite_create(
        payload: FavoriteCreatePayload,
        x_player_code: str | None = Header(default=None, alias="X-Player-Code"),
        x_role_token: str | None = Header(default=None, alias="X-Role-Token"),
        player_code: str | None = None,
        role_token: str | None = None,
    ):
        with connect(runtime_settings) as connection:
            _require_player_or_master(
                connection,
                player_id=payload.sorceress_id,
                allowed_roles={"sorceress"},
                player_code=x_player_code or player_code,
                role_token=x_role_token or role_token,
            )
            _reconcile_due_timers(connection, runtime_settings)
            try:
                return create_favorite_request(
                    connection,
                    sorceress_id=payload.sorceress_id,
                    favored_player_id=payload.favored_player_id,
                    slot=payload.slot,
                    favorite_id=payload.favorite_id,
                    passive_bonus_requested=payload.passive_bonus_requested,
                    source=payload.source,
                )
            except SorceressError as exc:
                raise _sorceress_http_error(exc) from exc

    @api.post("/api/favorites/{favorite_id}/accept")
    def favorite_accept(
        favorite_id: str,
        payload: FavoriteAcceptPayload,
        x_player_code: str | None = Header(default=None, alias="X-Player-Code"),
        x_role_token: str | None = Header(default=None, alias="X-Role-Token"),
        player_code: str | None = None,
        role_token: str | None = None,
    ):
        with connect(runtime_settings) as connection:
            _require_player_or_master(
                connection,
                player_id=payload.accepted_by_player_id,
                player_code=x_player_code or player_code,
                role_token=x_role_token or role_token,
            )
            _reconcile_due_timers(connection, runtime_settings)
            try:
                return accept_favorite(
                    connection,
                    favorite_id,
                    accepted_by_player_id=payload.accepted_by_player_id,
                    source=payload.source,
                )
            except SorceressError as exc:
                raise _sorceress_http_error(exc) from exc

    @api.post("/api/sorceresses/{sorceress_id}/alignment-evidence")
    def sorceress_alignment_evidence(
        sorceress_id: str,
        payload: AlignmentEvidencePayload,
        x_player_code: str | None = Header(default=None, alias="X-Player-Code"),
        x_role_token: str | None = Header(default=None, alias="X-Role-Token"),
        player_code: str | None = None,
        role_token: str | None = None,
    ):
        with connect(runtime_settings) as connection:
            _require_player_or_master(
                connection,
                player_id=sorceress_id,
                allowed_roles={"sorceress"},
                player_code=x_player_code or player_code,
                role_token=x_role_token or role_token,
            )
            _reconcile_due_timers(connection, runtime_settings)
            try:
                return record_alignment_evidence(
                    connection,
                    sorceress_id=sorceress_id,
                    alignment_state=payload.alignment_state,
                    evidence_type=payload.evidence_type,
                    payload=payload.payload,
                    visibility=payload.visibility,
                    final_flag=payload.final_flag,
                    source=payload.source,
                )
            except SorceressError as exc:
                raise _sorceress_http_error(exc) from exc

    @api.post("/api/pvp/challenges")
    def pvp_create_challenge(
        payload: PvpChallengePayload,
        x_player_code: str | None = Header(default=None, alias="X-Player-Code"),
        x_role_token: str | None = Header(default=None, alias="X-Role-Token"),
        player_code: str | None = None,
        role_token: str | None = None,
    ):
        with connect(runtime_settings) as connection:
            auth = _require_player_or_master(
                connection,
                player_id=payload.challenger_id,
                player_code=x_player_code or player_code,
                role_token=x_role_token or role_token,
            )
            if payload.master_approval and not auth["is_master"]:
                raise HTTPException(status_code=403, detail="Master approval requires master role token.")
            _reconcile_due_timers(connection, runtime_settings)
            try:
                return create_pvp_challenge(
                    connection,
                    ChallengeCreateInput(
                        challenge_id=payload.challenge_id,
                        challenger_id=payload.challenger_id,
                        target_id=payload.target_id,
                        stake=payload.stake,
                        mandatory=payload.mandatory,
                        master_approval=payload.master_approval,
                        source=payload.source,
                    ),
                )
            except PvpError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

    @api.get("/api/pvp/tables")
    def pvp_tables():
        with connect(runtime_settings) as connection:
            _reconcile_due_timers(connection, runtime_settings)
            return get_pvp_tables(connection)

    @api.get("/api/pvp/player-state")
    def pvp_player_state(
        player_id: str | None = None,
        x_player_code: str | None = Header(default=None, alias="X-Player-Code"),
        x_role_token: str | None = Header(default=None, alias="X-Role-Token"),
        player_code: str | None = None,
        role_token: str | None = None,
    ):
        with connect(runtime_settings) as connection:
            auth = _require_actor_context(
                connection,
                player_code=x_player_code or player_code,
                role_token=x_role_token or role_token,
            )
            effective_player_id = player_id if auth["is_master"] and player_id else auth["player_id"]
            if not effective_player_id:
                raise HTTPException(status_code=400, detail="player_id is required.")
            _reconcile_due_timers(connection, runtime_settings)
            try:
                return get_player_pvp_state(connection, str(effective_player_id))
            except PvpError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

    @api.post("/api/pvp/challenges/{challenge_id}/start")
    def pvp_start_challenge(
        challenge_id: str,
        payload: PvpStartPayload,
        x_player_code: str | None = Header(default=None, alias="X-Player-Code"),
        x_role_token: str | None = Header(default=None, alias="X-Role-Token"),
        player_code: str | None = None,
        role_token: str | None = None,
    ):
        with connect(runtime_settings) as connection:
            auth = _require_actor_context(
                connection,
                player_code=x_player_code or player_code,
                role_token=x_role_token or role_token,
            )
            _require_pvp_challenge_participant(connection, challenge_id, auth)
            if payload.master_approval and not auth["is_master"]:
                raise HTTPException(status_code=403, detail="Master approval requires master role token.")
            _reconcile_due_timers(connection, runtime_settings)
            try:
                return start_pvp_challenge(
                    connection,
                    ChallengeStartInput(
                        challenge_id=challenge_id,
                        master_approval=payload.master_approval,
                        mulligans_by_player=payload.mulligans_by_player,
                        deck_ids_by_player=payload.deck_ids_by_player,
                        preferred_starting_player_id=payload.preferred_starting_player_id,
                        source=payload.source,
                    ),
                )
            except PvpError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

    @api.post("/api/pvp/challenges/{challenge_id}/ready")
    def pvp_prepare_challenge(
        challenge_id: str,
        payload: GwentPreparationPayload,
        x_player_code: str | None = Header(default=None, alias="X-Player-Code"),
        x_role_token: str | None = Header(default=None, alias="X-Role-Token"),
        player_code: str | None = None,
        role_token: str | None = None,
    ):
        with connect(runtime_settings) as connection:
            auth = _require_actor_context(
                connection,
                player_code=x_player_code or player_code,
                role_token=x_role_token or role_token,
            )
            _require_pvp_challenge_participant(connection, challenge_id, auth)
            if auth["is_master"] or not auth["player_id"]:
                raise HTTPException(status_code=400, detail="Player code is required for Gwent preparation.")
            _reconcile_due_timers(connection, runtime_settings)
            try:
                return prepare_gwent_challenge(
                    connection,
                    GwentPreparationInput(
                        challenge_id=challenge_id,
                        player_id=str(auth["player_id"]),
                        mulligans=payload.mulligans,
                        deck_id=payload.deck_id,
                        preferred_starting_player_id=payload.preferred_starting_player_id,
                        source=payload.source,
                    ),
                )
            except PvpError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

    @api.post("/api/pvp/bot-match")
    def pvp_start_bot_match(
        payload: GwentBotMatchPayload,
        x_player_code: str | None = Header(default=None, alias="X-Player-Code"),
        x_role_token: str | None = Header(default=None, alias="X-Role-Token"),
        player_code: str | None = None,
        role_token: str | None = None,
    ):
        with connect(runtime_settings) as connection:
            auth = _require_actor_context(
                connection,
                player_code=x_player_code or player_code,
                role_token=x_role_token or role_token,
            )
            if auth["is_master"] or not auth["player_id"]:
                raise HTTPException(status_code=400, detail="Player code is required for bot Gwent match.")
            _reconcile_due_timers(connection, runtime_settings)
            try:
                return start_gwent_bot_match(
                    connection,
                    GwentBotMatchInput(
                        player_id=str(auth["player_id"]),
                        mulligans=payload.mulligans,
                        deck_id=payload.deck_id,
                        source=payload.source,
                    ),
                )
            except PvpError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

    @api.post("/api/pvp/decks")
    def pvp_save_gwent_deck(
        payload: GwentDeckSavePayload,
        x_player_code: str | None = Header(default=None, alias="X-Player-Code"),
        x_role_token: str | None = Header(default=None, alias="X-Role-Token"),
        player_code: str | None = None,
        role_token: str | None = None,
    ):
        with connect(runtime_settings) as connection:
            auth = _require_actor_context(
                connection,
                player_code=x_player_code or player_code,
                role_token=x_role_token or role_token,
            )
            if auth["is_master"] or not auth["player_id"]:
                raise HTTPException(status_code=400, detail="Player code is required for Gwent deck save.")
            _reconcile_due_timers(connection, runtime_settings)
            try:
                return save_gwent_runtime_deck(
                    connection,
                    GwentDeckSaveInput(
                        player_id=str(auth["player_id"]),
                        deck_id=payload.deck_id,
                        leader_card_id=payload.leader_card_id,
                        card_ids=payload.card_ids,
                        source=payload.source,
                    ),
                )
            except PvpError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

    @api.post("/api/pvp/matches/{match_id}/rounds")
    def pvp_record_round(
        match_id: str,
        payload: GwentRoundPayload,
        x_player_code: str | None = Header(default=None, alias="X-Player-Code"),
        x_role_token: str | None = Header(default=None, alias="X-Role-Token"),
        player_code: str | None = None,
        role_token: str | None = None,
    ):
        round_state = dict(payload.round_state or {})
        if payload.plays is not None:
            round_state["plays"] = payload.plays
        if payload.passed is not None:
            round_state["passed"] = payload.passed
        with connect(runtime_settings) as connection:
            auth = _require_actor_context(
                connection,
                player_code=x_player_code or player_code,
                role_token=x_role_token or role_token,
            )
            _require_gwent_match_participant(connection, match_id, auth)
            match_exists = connection.execute(
                "SELECT 1 FROM gwent_runtime_matches WHERE match_id = ?",
                (match_id,),
            ).fetchone()
            if match_exists is None:
                raise HTTPException(status_code=400, detail=f"Unknown Gwent match: {match_id}")
            if not auth["is_master"]:
                raise HTTPException(
                    status_code=403,
                    detail="Round submission is reserved for master correction; use /actions for gameplay.",
                )
            _assert_round_payload_actor_scope(round_state, auth)
            _reconcile_due_timers(connection, runtime_settings)
            try:
                return record_gwent_round(
                    connection,
                    match_id,
                    round_state,
                    round_number=payload.round_number,
                    actor_id=None if auth["is_master"] else auth["player_id"],
                    master_override=auth["is_master"],
                    source=payload.source,
                )
            except PvpError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

    @api.post("/api/pvp/matches/{match_id}/actions")
    def pvp_record_action(
        match_id: str,
        payload: GwentActionPayload,
        x_player_code: str | None = Header(default=None, alias="X-Player-Code"),
        x_role_token: str | None = Header(default=None, alias="X-Role-Token"),
        player_code: str | None = None,
        role_token: str | None = None,
    ):
        with connect(runtime_settings) as connection:
            auth = _require_actor_context(
                connection,
                player_code=x_player_code or player_code,
                role_token=x_role_token or role_token,
            )
            _require_gwent_match_participant(connection, match_id, auth)
            actor_id = auth["player_id"]
            if not actor_id:
                raise HTTPException(status_code=400, detail="player_id is required for Gwent action.")
            _reconcile_due_timers(connection, runtime_settings)
            try:
                return record_gwent_action(
                    connection,
                    GwentActionInput(
                        match_id=match_id,
                        player_id=str(actor_id),
                        action=payload.action,
                        round_number=payload.round_number,
                        card_id=payload.card_id,
                        row=payload.row,
                        target_card_id=payload.target_card_id,
                        discard_card_ids=payload.discard_card_ids,
                        revive_card_id=payload.revive_card_id,
                        revive_row=payload.revive_row,
                        action_id=payload.action_id,
                        source=payload.source,
                    ),
                )
            except PvpError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

    @api.post("/api/pvp/matches/{match_id}/finish")
    def pvp_finish_match(
        match_id: str,
        payload: GwentFinishPayload,
        x_player_code: str | None = Header(default=None, alias="X-Player-Code"),
        x_role_token: str | None = Header(default=None, alias="X-Role-Token"),
        player_code: str | None = None,
        role_token: str | None = None,
    ):
        with connect(runtime_settings) as connection:
            auth = _require_actor_context(
                connection,
                player_code=x_player_code or player_code,
                role_token=x_role_token or role_token,
            )
            _require_gwent_match_participant(connection, match_id, auth)
            if payload.winner_id and not auth["is_master"] and payload.winner_id != auth["player_id"]:
                raise HTTPException(status_code=403, detail="Winner payload must match authenticated player.")
            _reconcile_due_timers(connection, runtime_settings)
            try:
                return finish_gwent_match(
                    connection,
                    match_id,
                    winner_id=payload.winner_id,
                    outcome=payload.outcome,
                    source=payload.source,
                )
            except PvpError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

    @api.post("/api/pvp/challenges/{challenge_id}/refusal")
    def pvp_record_refusal(
        challenge_id: str,
        payload: PvpRefusalPayload,
        x_player_code: str | None = Header(default=None, alias="X-Player-Code"),
        x_role_token: str | None = Header(default=None, alias="X-Role-Token"),
        player_code: str | None = None,
        role_token: str | None = None,
    ):
        with connect(runtime_settings) as connection:
            auth = _require_actor_context(
                connection,
                player_code=x_player_code or player_code,
                role_token=x_role_token or role_token,
            )
            _require_pvp_challenge_participant(connection, challenge_id, auth)
            actor_id = payload.actor_id or auth["player_id"]
            if not auth["is_master"] and actor_id != auth["player_id"]:
                raise HTTPException(status_code=403, detail="Refusal actor must match authenticated player.")
            _reconcile_due_timers(connection, runtime_settings)
            try:
                return record_pvp_refusal(
                    connection,
                    challenge_id,
                    reason=payload.reason,
                    actor_id=actor_id,
                    source=payload.source,
                )
            except PvpError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

    @api.post("/api/master/pvp-throttle")
    def master_pvp_throttle(
        payload: PvpThrottlePayload,
        x_role_token: str | None = Header(default=None, alias="X-Role-Token"),
        role_token: str | None = None,
    ):
        with connect(runtime_settings) as connection:
            _require_master_token(connection, x_role_token or role_token)
            try:
                return set_pvp_throttle_mode(
                    connection,
                    payload.mode,
                    operator=payload.operator,
                    source=payload.source,
                )
            except PvpError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

    @api.post("/api/pvp/card-conversions")
    def pvp_convert_card(
        payload: CardConversionPayload,
        x_player_code: str | None = Header(default=None, alias="X-Player-Code"),
        x_role_token: str | None = Header(default=None, alias="X-Role-Token"),
        player_code: str | None = None,
        role_token: str | None = None,
    ):
        with connect(runtime_settings) as connection:
            _require_player_or_master(
                connection,
                player_id=payload.player_id,
                player_code=x_player_code or player_code,
                role_token=x_role_token or role_token,
            )
            _reconcile_due_timers(connection, runtime_settings)
            try:
                return convert_personal_card_to_lord(
                    connection,
                    player_id=payload.player_id,
                    lord_id=payload.lord_id,
                    personal_card_id=payload.personal_card_id,
                    source=payload.source,
                )
            except PvpError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

    @api.post("/api/lord-battles")
    def lord_battle_create(
        payload: LordBattleCreatePayload,
        x_role_token: str | None = Header(default=None, alias="X-Role-Token"),
        role_token: str | None = None,
    ):
        with connect(runtime_settings) as connection:
            auth = _require_lord_battle_actor_token(connection, x_role_token or role_token)
            reconcile_pending_lord_moves(
                connection,
                domain_id=auth.domain_id if auth.role_type == "lord" else None,
            )
            try:
                return create_lord_battle(
                    connection,
                    battle_id=payload.battle_id,
                    attacker_domain_id=payload.attacker_domain_id,
                    attacker_lord_id=payload.attacker_lord_id,
                    defender_domain_id=payload.defender_domain_id,
                    defender_lord_id=payload.defender_lord_id,
                    territory_id=payload.territory_id,
                    claim_id=payload.claim_id,
                    seed=payload.seed,
                    actor_domain_id=auth.domain_id,
                    actor_role_type=auth.role_type,
                    source=payload.source,
                )
            except LordBattleError as exc:
                raise _battle_http_error(exc) from exc

    @api.get("/api/lord-battles")
    def lord_battle_list(
        domain_id: str | None = None,
        x_role_token: str | None = Header(default=None, alias="X-Role-Token"),
        role_token: str | None = None,
    ):
        with connect(runtime_settings) as connection:
            auth = _require_lord_battle_actor_token(connection, x_role_token or role_token)
            reconcile_pending_lord_moves(
                connection,
                domain_id=auth.domain_id if auth.role_type == "lord" else None,
            )
            scoped_domain_id = domain_id
            if auth.role_type == "lord":
                if domain_id and domain_id != auth.domain_id:
                    raise HTTPException(status_code=403, detail="Token cannot list this lord battle domain.")
                scoped_domain_id = auth.domain_id
            return list_lord_battles(
                connection,
                domain_id=scoped_domain_id,
                viewer_domain_id=auth.domain_id,
                viewer_role_type=auth.role_type,
            )

    @api.get("/api/lord-battles/{battle_id}")
    def lord_battle_get(
        battle_id: str,
        x_role_token: str | None = Header(default=None, alias="X-Role-Token"),
        role_token: str | None = None,
    ):
        with connect(runtime_settings) as connection:
            auth = _require_lord_battle_actor_token(connection, x_role_token or role_token)
            reconcile_pending_lord_moves(
                connection,
                domain_id=auth.domain_id if auth.role_type == "lord" else None,
            )
            try:
                battle = get_lord_battle(
                    connection,
                    battle_id,
                    viewer_domain_id=auth.domain_id,
                    viewer_role_type=auth.role_type,
                )
                _assert_lord_battle_visible_to_auth(battle, auth)
                return battle
            except LordBattleError as exc:
                raise _battle_http_error(exc) from exc

    @api.post("/api/lord-battles/{battle_id}/actions")
    def lord_battle_action(
        battle_id: str,
        payload: LordBattleActionPayload,
        x_role_token: str | None = Header(default=None, alias="X-Role-Token"),
        role_token: str | None = None,
    ):
        with connect(runtime_settings) as connection:
            auth = _require_lord_battle_actor_token(connection, x_role_token or role_token)
            reconcile_pending_lord_moves(
                connection,
                domain_id=auth.domain_id if auth.role_type == "lord" else None,
            )
            actor_domain_id = auth.domain_id if auth.role_type == "lord" else payload.actor_domain_id
            try:
                return record_lord_battle_action(
                    connection,
                    battle_id,
                    action_type=payload.action_type,
                    actor_side=payload.actor_side,
                    action_id=payload.action_id,
                    actor_domain_id=actor_domain_id,
                    actor_role_type=auth.role_type,
                    payload=payload.payload,
                    source=payload.source,
                )
            except LordBattleError as exc:
                raise _battle_http_error(exc) from exc

    return api


def _require_actor_context(
    connection,
    *,
    player_code: str | None = None,
    role_token: str | None = None,
) -> dict[str, Any]:
    if role_token and role_token.strip():
        auth = authenticate_role_token(connection, role_token)
        if auth is None:
            raise HTTPException(status_code=401, detail="Invalid role token.")
        is_master = auth.role_type == "npc_master"
        return {
            "scope": "role_token",
            "is_master": is_master,
            "player_id": auth.owner_id,
            "actor_id": auth.owner_id,
            "role_type": auth.role_type,
            "event_actor_type": "master" if is_master else auth.role_type,
            "domain_id": auth.domain_id,
            "token_id": auth.token_id,
        }

    if player_code and player_code.strip():
        auth = _authenticate_player_code(connection, player_code)
        if auth is None:
            raise HTTPException(status_code=401, detail="Invalid player code.")
        role_type = str(auth["role_type"])
        return {
            "scope": "player_code",
            "is_master": False,
            "player_id": str(auth["player_id"]),
            "actor_id": str(auth["player_id"]),
            "role_type": role_type,
            "event_actor_type": role_type,
            "domain_id": auth["player"].get("lord_id") if isinstance(auth.get("player"), dict) else None,
            "player_code_id": auth.get("player_code_id"),
        }

    raise HTTPException(status_code=401, detail="Player code or role token is required.")


def _require_player_or_master(
    connection,
    *,
    player_id: str,
    allowed_roles: set[str] | None = None,
    player_code: str | None = None,
    role_token: str | None = None,
) -> dict[str, Any]:
    auth = _require_actor_context(
        connection,
        player_code=player_code,
        role_token=role_token,
    )
    if auth["is_master"]:
        return auth
    if auth["player_id"] != player_id:
        raise HTTPException(status_code=403, detail="Authenticated player cannot mutate this resource.")
    if allowed_roles is not None and auth["role_type"] not in allowed_roles:
        raise HTTPException(status_code=403, detail="Authenticated role cannot access this resource.")
    return auth


def _reconcile_due_timers(connection, settings: Settings) -> None:
    apply_due_timers(connection, settings, source="role_endpoint_reconcile")


def _require_pvp_challenge_participant(
    connection,
    challenge_id: str,
    auth: dict[str, Any],
) -> None:
    if auth["is_master"]:
        return
    try:
        row = connection.execute(
            """
            SELECT challenger_id, target_id
            FROM pvp_challenges
            WHERE challenge_id = ?
            """,
            (challenge_id,),
        ).fetchone()
    except sqlite3.OperationalError:
        row = None
    if row is None:
        return
    if auth["player_id"] not in {str(row["challenger_id"]), str(row["target_id"])}:
        raise HTTPException(status_code=403, detail="Authenticated player is not part of this PvP challenge.")


def _require_gwent_match_participant(
    connection,
    match_id: str,
    auth: dict[str, Any],
) -> None:
    if auth["is_master"]:
        return
    try:
        row = connection.execute(
            """
            SELECT challenger_id, target_id
            FROM gwent_runtime_matches
            WHERE match_id = ?
            """,
            (match_id,),
        ).fetchone()
    except sqlite3.OperationalError:
        row = None
    if row is None:
        return
    if auth["player_id"] not in {str(row["challenger_id"]), str(row["target_id"])}:
        raise HTTPException(status_code=403, detail="Authenticated player is not part of this Gwent match.")


def _assert_round_payload_actor_scope(
    round_state: dict[str, Any],
    auth: dict[str, Any],
) -> None:
    if auth["is_master"]:
        return
    actor_id = auth["player_id"]
    plays = round_state.get("plays", [])
    if isinstance(plays, list):
        for play in plays:
            if isinstance(play, dict) and str(play.get("player_id")) != actor_id:
                raise HTTPException(status_code=403, detail="Round play player_id must match authenticated player.")
    passed = round_state.get("passed", {})
    if isinstance(passed, dict):
        for player_id in passed:
            if str(player_id) != actor_id:
                raise HTTPException(status_code=403, detail="Round passed payload must match authenticated player.")


def _assert_lord_battle_visible_to_auth(battle: dict[str, Any], auth) -> None:
    if auth.role_type == "npc_master":
        return
    domain_id = auth.domain_id
    if not domain_id:
        raise HTTPException(status_code=403, detail="Lord token is not assigned to a domain.")
    visible_domains = {
        str(battle.get("attacker_domain_id") or ""),
        str(battle.get("defender_domain_id") or ""),
    }
    if domain_id not in visible_domains:
        raise HTTPException(status_code=403, detail="Token cannot access this lord battle.")


def _require_lord_token(
    connection,
    lord_id: str,
    token: str | None,
) -> None:
    if not token:
        raise HTTPException(status_code=401, detail="Role token is required.")
    auth = _authenticate_role_token_or_lord_code(connection, token)
    if auth is None:
        raise HTTPException(status_code=401, detail="Invalid role token.")
    if auth.role_type != "lord" or auth.owner_id != lord_id:
        raise HTTPException(status_code=403, detail="Token cannot access this lord.")


def _require_master_token(connection, token: str | None) -> None:
    if not token:
        raise HTTPException(status_code=401, detail="Master role token is required.")
    auth = authenticate_role_token(connection, token)
    if auth is None:
        raise HTTPException(status_code=401, detail="Invalid role token.")
    if auth.role_type != "npc_master":
        raise HTTPException(status_code=403, detail="Token cannot access master API.")


def _require_lord_battle_actor_token(connection, token: str | None):
    if not token:
        raise HTTPException(status_code=401, detail="Role token is required.")
    auth = _authenticate_role_token_or_lord_code(connection, token)
    if auth is None:
        raise HTTPException(status_code=401, detail="Invalid role token.")
    if auth.role_type not in {"lord", "npc_master"}:
        raise HTTPException(status_code=403, detail="Token cannot access lord battle API.")
    if auth.role_type == "lord" and not auth.domain_id:
        raise HTTPException(status_code=403, detail="Lord token is not assigned to a domain.")
    return auth


def _authenticate_role_token_or_lord_code(
    connection, token: str
) -> RoleTokenAuth | None:
    auth = authenticate_role_token(connection, token)
    if auth is not None:
        return auth

    player_auth = _authenticate_player_code(connection, token)
    if player_auth is None or player_auth["role_type"] != "lord":
        return None

    player = player_auth.get("player", {})
    domain_id = str(player.get("lord_id") or "") or None
    return RoleTokenAuth(
        token_id=str(player_auth["player_code_id"]),
        role_type="lord",
        owner_id=str(player_auth["player_id"]),
        display_name=str(player_auth["display_name"]),
        lord_id=str(player_auth["player_id"]),
        domain_id=domain_id,
        permissions=["lord_panel:read"],
    )


def _authenticate_player_code(connection, player_code: str) -> dict[str, Any] | None:
    normalized = player_code.strip().upper()
    if not normalized:
        return None
    try:
        row = connection.execute(
            """
            SELECT
                pc.code_id,
                pc.player_id,
                pc.enabled,
                p.role_type,
                p.display_name,
                p.lord_id,
                p.sorceress_start_lord_id,
                p.level,
                p.xp,
                p.gold,
                p.stats_json
            FROM player_codes pc
            JOIN players p ON p.player_id = pc.player_id
            WHERE UPPER(pc.code) = ?
            """,
            (normalized,),
        ).fetchone()
    except sqlite3.OperationalError:
        return None
    if row is None or str(row["enabled"]).lower() != "true":
        return None
    player = {
        "player_id": str(row["player_id"]),
        "role_type": str(row["role_type"]),
        "display_name": str(row["display_name"]),
        "lord_id": str(row["lord_id"]),
        "sorceress_start_lord_id": str(row["sorceress_start_lord_id"]),
        "level": str(row["level"]),
        "xp": str(row["xp"]),
        "gold": str(row["gold"]),
        "stats_json": str(row["stats_json"]),
    }
    reputation_state = _player_auth_reputation_state(connection, str(row["player_id"]))
    if reputation_state:
        player["reputation_state"] = reputation_state
    return {
        "status": "ok",
        "scope": "player",
        "player_code_id": str(row["code_id"]),
        "player_id": str(row["player_id"]),
        "role_type": str(row["role_type"]),
        "display_name": str(row["display_name"]),
        "player": player,
        "permissions": ["mobile:snapshot", "mobile:event_sync"],
    }


def _player_auth_reputation_state(
    connection, player_id: str
) -> dict[str, object] | None:
    try:
        view = get_reputation_view(connection, player_id, visibility="player")
    except (ReputationError, sqlite3.OperationalError):
        return None
    return {
        key: view[key]
        for key in (
            "state_label",
            "canonical_label",
            "player_descriptor",
            "value_visibility",
        )
        if key in view
    }


def _build_mobile_qr_order_check(
    connection,
    *,
    player_id: str,
    code: str,
    device_id: str | None,
    source: str,
) -> dict[str, object]:
    normalized_code = normalize_qr_code(code)
    source_type = source if source in {"qr_scan", "manual_id"} else "qr_scan"
    qr = _fetch_mobile_qr_by_code(connection, normalized_code)
    if qr is None:
        return {
            "status": "unknown_qr",
            "allowed": False,
            "message": "Unknown QR/manual ID.",
            "normalized_code": normalized_code,
            "source": source_type,
            "device_id": device_id,
        }

    if _mobile_qr_act_locked(connection, qr):
        return {
            "status": "act_locked",
            "allowed": False,
            "message": "QR is locked until this act opens.",
            "normalized_code": normalized_code,
            "source": source_type,
            "device_id": device_id,
        }

    scenario = _fetch_mobile_row_by_id(
        connection,
        "pve_scenarios",
        "scenario_id",
        str(qr.get("scenario_id", "")),
    )
    order = _matching_mobile_order_for_qr(
        connection,
        player_id=player_id,
        qr=qr,
        scenario=scenario or {},
    )
    if order is None:
        return {
            "status": "not_taken",
            "allowed": False,
            "message": "QR is not linked to an active order for this player.",
            "normalized_code": normalized_code,
            "source": source_type,
            "device_id": device_id,
        }

    object_label, object_type = _mobile_order_object_metadata(connection, str(order.get("object_id", "")), qr)
    return {
        "status": "matched_order",
        "allowed": True,
        "normalized_code": normalized_code,
        "source": source_type,
        "device_id": device_id,
        "qr": {
            "qr_id": str(qr.get("qr_id", "")),
            "manual_code": str(qr.get("manual_code", "")),
            "qr_mode": str(qr.get("qr_mode", "")),
            "act_id": str(qr.get("act_id", "")),
            "scenario_id": str(qr.get("scenario_id", "")),
            "location_node_id": str(qr.get("location_node_id", "")),
        },
        "order": {
            "order_id": str(order.get("order_id", "")),
            "lord_id": str(order.get("lord_id", "")),
            "target_player_id": str(order.get("target_player_id", "")),
            "object_id": str(order.get("object_id", "")),
            "object_label": object_label,
            "object_type": object_type,
            "title": object_label,
            "status": str(order.get("status", "")),
            "visibility": str(order.get("visibility", "")),
        },
        "quest": _mobile_quest_payload(scenario),
    }


def _fetch_mobile_qr_by_code(
    connection,
    normalized_code: str,
) -> dict[str, object] | None:
    if not normalized_code:
        return None
    row = connection.execute(
        """
        SELECT *
        FROM qr_objects
        WHERE UPPER(manual_code) = ?
        LIMIT 1
        """,
        (normalized_code,),
    ).fetchone()
    return _mobile_row_to_dict(row)


def _matching_mobile_order_for_qr(
    connection,
    *,
    player_id: str,
    qr: dict[str, object],
    scenario: dict[str, object],
) -> dict[str, object] | None:
    for order in _active_mobile_orders_for_player(connection, player_id):
        if _mobile_order_matches_qr(connection, order, qr, scenario):
            return order
    return None


def _active_mobile_orders_for_player(connection, player_id: str) -> list[dict[str, object]]:
    rows_by_id: dict[str, dict[str, object]] = {}
    if _mobile_table_exists(connection, "orders"):
        for row in connection.execute("SELECT * FROM orders").fetchall():
            order = _mobile_row_to_dict(row)
            if order is not None:
                rows_by_id[str(order.get("order_id", ""))] = order
    if _mobile_table_exists(connection, "order_runtime_state"):
        for row in connection.execute("SELECT * FROM order_runtime_state").fetchall():
            order = _mobile_row_to_dict(row)
            if order is not None:
                rows_by_id[str(order.get("order_id", ""))] = order

    result: list[dict[str, object]] = []
    for order in rows_by_id.values():
        if _mobile_order_is_active_for_player(order, player_id):
            result.append(order)
    return result


def _mobile_order_is_active_for_player(order: dict[str, object], player_id: str) -> bool:
    status = str(order.get("status", "")).strip().lower()
    if status in {"completed", "cancelled", "rejected", "failed", "contested_review"}:
        return False
    if not player_id:
        return False
    return player_id in {
        str(order.get("target_player_id", "")),
        str(order.get("accepted_by_player_id", "")),
        str(order.get("submitted_by_player_id", "")),
    }


def _mobile_order_matches_qr(
    connection,
    order: dict[str, object],
    qr: dict[str, object],
    scenario: dict[str, object],
) -> bool:
    object_id = str(order.get("object_id", "")).strip().upper()
    if not object_id:
        return False
    interest = _fetch_mobile_row_by_id(
        connection,
        "order_interest_objects",
        "interest_id",
        str(order.get("object_id", "")).strip(),
    )
    if interest is not None:
        return object_id == str(interest.get("interest_id", "")).strip().upper() and str(
            interest.get("qr_id", "")
        ).strip().upper() == str(qr.get("qr_id", "")).strip().upper()
    node_id = str(qr.get("location_node_id", ""))
    values = {
        str(qr.get("qr_id", "")),
        str(qr.get("manual_code", "")),
        node_id,
        str(qr.get("scenario_id", "")),
        str(scenario.get("scenario_id", "")),
        _mobile_territory_id_for_node(connection, node_id),
    }
    return object_id in {value.strip().upper() for value in values if value}


def _mobile_order_object_metadata(
    connection,
    object_id: str,
    qr: dict[str, object],
) -> tuple[str, str]:
    interest = _fetch_mobile_row_by_id(connection, "order_interest_objects", "interest_id", object_id)
    if interest is not None:
        return (
            str(interest.get("display_name") or object_id),
            str(interest.get("interest_type") or "order_interest"),
        )

    territory = _fetch_mobile_row_by_id(connection, "territories", "territory_id", object_id)
    if territory is not None:
        return str(territory.get("name", object_id)), "territory"

    if object_id == str(qr.get("qr_id", "")):
        node = _fetch_mobile_row_by_id(
            connection,
            "map_nodes",
            "node_id",
            str(qr.get("location_node_id", "")),
        )
        if node is not None:
            return str(node.get("name", object_id)), "qr_object"
        return object_id, "qr_object"

    return object_id, "unknown"


def _mobile_quest_payload(scenario: dict[str, object] | None) -> dict[str, object]:
    if not scenario:
        return {}
    primary_stat = str(scenario.get("primary_stat", ""))
    dc = str(scenario.get("dc", ""))
    success_text = str(scenario.get("success_text", ""))
    memo_parts = []
    if primary_stat and dc:
        memo_parts.append(f"{primary_stat} vs {dc}")
    if success_text:
        memo_parts.append(success_text)
    return {
        "scenario_id": str(scenario.get("scenario_id", "")),
        "scene_type": str(scenario.get("scene_type", "")),
        "primary_stat": primary_stat,
        "dc": dc,
        "success_text": success_text,
        "failure_text": str(scenario.get("failure_text", "")),
        "timeout_outcome": str(scenario.get("timeout_outcome", "")),
        "memo": " · ".join(memo_parts),
    }


def _mobile_qr_act_locked(connection, qr: dict[str, object]) -> bool:
    act_id = str(qr.get("act_id", ""))
    if not act_id or act_id == "act1":
        return False
    act = _fetch_mobile_row_by_id(connection, "acts", "act_id", act_id)
    if act is not None and str(act.get("unlock_required", "")).strip().lower() != "true":
        return False
    if not _mobile_table_exists(connection, "act_history"):
        return True
    row = connection.execute(
        """
        SELECT physical_announcement_state, unlock_revealed_at
        FROM act_history
        WHERE act_id = ?
        """,
        (act_id,),
    ).fetchone()
    if row is None:
        return True
    return not (
        _mobile_is_announced(row["physical_announcement_state"])
        or bool(row["unlock_revealed_at"])
    )


def _mobile_territory_id_for_node(connection, node_id: str) -> str:
    if not node_id:
        return ""
    row = connection.execute(
        """
        SELECT territory_id
        FROM map_nodes
        WHERE node_id = ?
        LIMIT 1
        """,
        (node_id,),
    ).fetchone()
    return str(row["territory_id"]) if row is not None else ""


def _fetch_mobile_row_by_id(
    connection,
    table: str,
    column: str,
    value: str,
) -> dict[str, object] | None:
    if not value or not _mobile_table_exists(connection, table):
        return None
    row = connection.execute(
        f'SELECT * FROM "{table}" WHERE "{column}" = ? LIMIT 1',
        (value,),
    ).fetchone()
    return _mobile_row_to_dict(row)


def _mobile_row_to_dict(row) -> dict[str, object] | None:
    if row is None:
        return None
    return {
        key: row[key]
        for key in row.keys()
        if key not in {"_import_run_id", "_row_number"}
    }


def _mobile_table_exists(connection, table: str) -> bool:
    row = connection.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table' AND name = ?
        """,
        (table,),
    ).fetchone()
    return row is not None


def _mobile_is_announced(value: object) -> bool:
    return str(value or "").strip().lower() in {
        "announced",
        "completed",
        "done",
        "physical_announced",
    }


def _lord_http_error(exc: LordRuntimeError):
    return HTTPException(
        status_code=exc.status_code,
        detail={"code": exc.code, "reason_code": exc.code, "message": str(exc)},
    )


def _order_reward_id(
    connection: sqlite3.Connection, reward: str | dict[str, Any] | None
) -> str | None:
    if reward is None:
        return None
    if isinstance(reward, str):
        return reward.strip() or None
    for key in ("reward_id", "id", "escrow_reward_id"):
        value = reward.get(key)
        if value:
            return str(value)
    gold = _order_reward_gold(reward)
    if gold:
        return _ensure_order_gold_reward(connection, gold)
    return None


def _order_reward_gold(reward: dict[str, Any]) -> int:
    for key in ("gold", "gold_amount", "amount"):
        raw_value = reward.get(key)
        if raw_value in {None, ""}:
            continue
        try:
            value = int(float(str(raw_value).replace(",", ".")))
        except (TypeError, ValueError):
            return 0
        return max(0, value)
    return 0


def _ensure_order_gold_reward(connection: sqlite3.Connection, gold: int) -> str:
    reward_id = f"order_gold_{gold}"
    existing = connection.execute(
        "SELECT 1 FROM rewards WHERE reward_id = ? LIMIT 1",
        (reward_id,),
    ).fetchone()
    if existing is not None:
        return reward_id

    try:
        connection.execute(
            """
            INSERT OR IGNORE INTO rewards (
                _import_run_id, _row_number, reward_id, xp, gold, item_ids, card_ids,
                artifact_ids, rarity, approval_policy
            )
            VALUES ('runtime_order_gold', ?, ?, '0', ?, '', '', '', 'Common', 'pending_master_approval')
            """,
            (gold, reward_id, str(gold)),
        )
    except sqlite3.OperationalError as exc:
        raise LordRuntimeError(
            "missing_escrow_reward",
            "Order gold reward catalog is not available.",
        ) from exc
    return reward_id


def _with_lord_order_state(
    connection: sqlite3.Connection, lord_id: str, result: dict[str, Any]
) -> dict[str, Any]:
    state = build_lord_state(connection, lord_id) or {}
    return {
        **result,
        "orders": state.get("orders", []),
        "order_cap": state.get("order_cap"),
        "escrow": state.get("escrow"),
        "order_conflicts": state.get("order_conflicts", []),
    }


def _battle_http_error(exc: LordBattleError):
    return HTTPException(
        status_code=exc.status_code,
        detail={"code": exc.code, "message": str(exc)},
    )


def _sorceress_http_error(exc: SorceressError):
    return HTTPException(
        status_code=exc.status_code,
        detail={"code": exc.code, "message": str(exc)},
    )


def _material_market_http_error(exc: MaterialMarketError):
    return HTTPException(
        status_code=exc.status_code,
        detail={"code": exc.code, "message": str(exc)},
    )


def _asset_http_error(exc: AssetContractError):
    return HTTPException(
        status_code=exc.status_code,
        detail={"code": exc.code, "message": str(exc)},
    )


def _game_ops_http_error(exc: GameOpsCorrectionError):
    return HTTPException(
        status_code=exc.status_code,
        detail={"code": exc.code, "message": exc.message},
    )


def _suggested_lan_server_url(request: Request) -> str:
    scheme = request.url.scheme or "http"
    host = request.url.hostname or "127.0.0.1"
    port = f":{request.url.port}" if request.url.port else ""
    if host in {"127.0.0.1", "localhost", "0.0.0.0"}:
        host = _local_ipv4_address() or host
    return f"{scheme}://{host}{port}"


def _suggested_player_login_url(request: Request) -> str:
    server_url = _suggested_lan_server_url(request)
    return f"{server_url}/lords/login"


def _local_ipv4_address() -> str | None:
    try:
        addresses = socket.gethostbyname_ex(socket.gethostname())[2]
    except OSError:
        return None
    for address in addresses:
        if address.startswith(("10.", "172.", "192.168.")):
            return address
    return addresses[0] if addresses else None


app = create_app() if FastAPI is not None else None
