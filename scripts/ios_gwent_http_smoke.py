#!/usr/bin/env python3
"""Run an HTTP smoke for the iOS Gwent two-player flow against a live server."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import sys
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class SmokeError(RuntimeError):
    """Raised when the smoke cannot complete the expected flow."""


REQUIRED_API_REVISION = "ios-gwent-pvp-v1"
REQUIRED_API_FEATURES = {
    "ios_gwent_bot_match",
    "ios_gwent_deckbuilder",
    "ios_gwent_pvp_actions",
    "ios_gwent_preflight",
    "ios_gwent_scoiatael_first_turn",
}


@dataclass(frozen=True)
class Player:
    player_id: str
    code: str


class ApiClient:
    def __init__(self, base_url: str, timeout: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def get(self, path: str, *, player_code: str | None = None) -> dict[str, Any]:
        return self._request("GET", path, player_code=player_code)

    def post(self, path: str, body: dict[str, Any], *, player_code: str | None = None) -> dict[str, Any]:
        return self._request("POST", path, body=body, player_code=player_code)

    def _request(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        player_code: str | None = None,
    ) -> dict[str, Any]:
        data = None if body is None else json.dumps(body).encode("utf-8")
        request = Request(
            f"{self.base_url}{path}",
            data=data,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        if player_code:
            request.add_header("X-Player-Code", player_code)
        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise SmokeError(f"{method} {path} failed with HTTP {exc.code}: {detail}") from exc
        except URLError as exc:
            raise SmokeError(f"{method} {path} failed: {exc}") from exc
        if not raw:
            return {}
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise SmokeError(f"{method} {path} returned non-JSON: {raw[:200]}") from exc
        if not isinstance(value, dict):
            raise SmokeError(f"{method} {path} returned non-object JSON: {value!r}")
        return value


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Smoke the live HTTP Gwent PvP flow used by the iOS client."
    )
    parser.add_argument("--server", default="http://192.168.68.118:8002", help="FastAPI base URL.")
    parser.add_argument("--p1-id", default="p_witcher_1")
    parser.add_argument("--p1-code", default="WC-WOLF-6GF4")
    parser.add_argument("--p1-deck-id", default="")
    parser.add_argument("--p1-starting-player-id", default="")
    parser.add_argument("--p2-id", default="p_witcher_2")
    parser.add_argument("--p2-code", default="WC-CAT-1HN8")
    parser.add_argument("--p2-deck-id", default="")
    parser.add_argument("--p2-starting-player-id", default="")
    parser.add_argument("--stake-gold", type=int, default=5)
    parser.add_argument("--challenge-id", default=f"ios-gwent-smoke-{int(time.time())}")
    parser.add_argument(
        "--bot",
        action="store_true",
        help="Run the one-player iOS training flow against the Gwent bot instead of a two-player challenge.",
    )
    parser.add_argument(
        "--bot-max-actions",
        type=int,
        default=40,
        help="Maximum human actions to send while waiting for a bot training match to finish.",
    )
    parser.add_argument(
        "--preflight-only",
        action="store_true",
        help="Only verify health, snapshot/auth, PvP tables and active-state guardrails; do not create a match.",
    )
    parser.add_argument("--timeout", type=float, default=8.0)
    parser.add_argument("--poll-seconds", type=float, default=0.5)
    parser.add_argument("--poll-attempts", type=int, default=20)
    parser.add_argument(
        "--json-report",
        help="Write a machine-readable report with challenge, match, rounds, finish and stake checks.",
    )
    parser.add_argument(
        "--skip-preflight",
        action="store_true",
        help="Do not check that selected players have no active PvP state before creating a challenge.",
    )
    parser.add_argument(
        "--skip-idempotency-check",
        action="store_true",
        help="Do not repeat the first card action to verify duplicate action_id handling.",
    )
    args = parser.parse_args(argv)

    client = ApiClient(args.server, args.timeout)
    p1 = Player(args.p1_id, args.p1_code)
    p2 = Player(args.p2_id, args.p2_code)
    report: dict[str, Any] = {
        "server": client.base_url,
        "mode": "bot" if args.bot else "pvp",
        "preflight_only": bool(args.preflight_only),
        "challenge_id": args.challenge_id,
        "players": {
            "p1": {
                "player_id": p1.player_id,
                "deck_id": args.p1_deck_id or None,
                "preferred_starting_player_id": args.p1_starting_player_id or None,
            },
            "p2": {
                "player_id": p2.player_id,
                "deck_id": args.p2_deck_id or None,
                "preferred_starting_player_id": args.p2_starting_player_id or None,
            },
        },
        "stake": {"asset_type": "gold", "asset_id": "gold", "amount": args.stake_gold},
        "rounds": [],
        "steps": [],
        "idempotency_checks": [],
        "started_at": int(time.time()),
    }

    try:
        if args.preflight_only:
            run_preflight(client, p1, None if args.bot else p2, args, report)
        elif args.bot:
            run_bot_smoke(client, p1, args, report)
        else:
            run_smoke(client, p1, p2, args, report)
    except SmokeError as exc:
        report["status"] = "failed"
        report["error"] = str(exc)
        write_json_report(args.json_report, report)
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    report["status"] = "passed"
    report["finished_at"] = int(time.time())
    write_json_report(args.json_report, report)
    if args.preflight_only:
        print("OK: iOS Gwent HTTP preflight completed without creating a challenge or match.")
    elif args.bot:
        print("OK: iOS Gwent bot HTTP smoke completed.")
    else:
        print("OK: iOS Gwent HTTP smoke completed.")
    return 0


def run_preflight(
    client: ApiClient,
    p1: Player,
    p2: Player | None,
    args: argparse.Namespace,
    report: dict[str, Any],
) -> None:
    print(f"Server: {client.base_url}")
    print("Preflight only: no challenge, bot match, stake or card action will be created")
    health = client.get("/health")
    expect(health.get("status") == "ok", "health endpoint did not report ok")
    database = health.get("database") if isinstance(health.get("database"), dict) else {}
    api = health.get("api") if isinstance(health.get("api"), dict) else {}
    features = api.get("features") if isinstance(api.get("features"), list) else []
    feature_set = {str(feature) for feature in features}
    expect(database.get("status") == "ok", "database health did not report ok")
    report["health"] = {
        "status": health.get("status"),
        "database_status": database.get("status"),
        "database_path": database.get("path"),
        "schema_version": database.get("schema_version"),
        "api_revision": api.get("revision"),
        "api_features": sorted(feature_set),
    }
    add_step(report, "health_ok", **report["health"])
    expect(
        api.get("revision") == REQUIRED_API_REVISION,
        "server API revision mismatch: "
        f"expected {REQUIRED_API_REVISION}, got {api.get('revision') or '-'}; "
        "restart the FastAPI server from the current iOS Gwent branch",
    )
    missing_features = sorted(REQUIRED_API_FEATURES - feature_set)
    expect(
        not missing_features,
        "server is missing required iOS Gwent API features: " + ", ".join(missing_features),
    )

    tables = client.get("/api/pvp/tables")
    table_rows = tables.get("tables")
    expect(isinstance(table_rows, list), "pvp tables response has no tables list")
    report["tables"] = {
        "count": len(table_rows),
        "open": sum(1 for table in table_rows if isinstance(table, dict) and table.get("status") == "open"),
    }
    add_step(report, "pvp_tables_ok", **report["tables"])

    players = [(p1, args.p1_deck_id)]
    if p2 is not None:
        players.append((p2, args.p2_deck_id))
    for player, deck_id in players:
        snapshot = client.get(
            f"/api/content/snapshot?player_code={player.code}",
            player_code=player.code,
        )
        verify_snapshot_for_player(snapshot, player, deck_id, report)
        state = preflight_player_clear(
            client,
            player,
            require_challenge_token=(p2 is not None and player.player_id == p1.player_id),
        )
        add_step(
            report,
            "player_preflight_clear",
            player_id=player.player_id,
            challenge_tokens=state.get("challenge_tokens"),
            can_create_challenge=state.get("can_create_challenge"),
        )
        print(f"preflight: {player.player_id} auth/snapshot/player-state ok")


def run_smoke(
    client: ApiClient,
    p1: Player,
    p2: Player,
    args: argparse.Namespace,
    report: dict[str, Any],
) -> None:
    print(f"Server: {client.base_url}")
    print(f"Challenge: {args.challenge_id}")
    if not args.skip_preflight:
        p1_state = preflight_player_clear(client, p1, require_challenge_token=True)
        p2_state = preflight_player_clear(client, p2)
        add_step(
            report,
            "preflight_clear",
            players=[p1.player_id, p2.player_id],
            challenge_tokens={
                p1.player_id: p1_state.get("challenge_tokens"),
                p2.player_id: p2_state.get("challenge_tokens"),
            },
        )
        print("preflight: selected players have no active PvP state")
    challenge = client.post(
        "/api/pvp/challenges",
        {
            "challenge_id": args.challenge_id,
            "challenger_id": p1.player_id,
            "target_id": p2.player_id,
            "stake": {"asset_type": "gold", "asset_id": "gold", "amount": args.stake_gold},
            "source": "ios_gwent_http_smoke",
        },
        player_code=p1.code,
    )
    expect(challenge.get("challenge_id") == args.challenge_id, "challenge id mismatch")
    add_step(report, "challenge_created", challenge_id=args.challenge_id)
    print("created challenge")

    p1_ready = client.post(
        f"/api/pvp/challenges/{args.challenge_id}/ready",
        ready_payload(args.p1_deck_id, args.p1_starting_player_id),
        player_code=p1.code,
    )
    expect(p1_ready.get("started") is False, "match started before both players were ready")
    add_step(report, "player_ready", player_id=p1.player_id, started=False)
    print("p1 ready")

    p2_ready = client.post(
        f"/api/pvp/challenges/{args.challenge_id}/ready",
        ready_payload(args.p2_deck_id, args.p2_starting_player_id),
        player_code=p2.code,
    )
    match = p2_ready.get("match")
    expect(isinstance(match, dict), "second ready did not start a match")
    match_id = str(match.get("match_id") or "")
    expect(bool(match_id), "started match has no match_id")
    report["match_id"] = match_id
    verify_selected_deck(match, p1, args.p1_deck_id, report)
    verify_selected_deck(match, p2, args.p2_deck_id, report)
    verify_selected_starting_player(match, args.p1_starting_player_id or args.p2_starting_player_id, report)
    add_step(report, "player_ready", player_id=p2.player_id, started=True, match_id=match_id)
    print(f"p2 ready, match {match_id}")

    for expected_round in (1, 2):
        first_player, first_state = wait_for_any_turn(client, (p1, p2), expected_round, args)
        round_report: dict[str, Any] = {
            "round_number": expected_round,
            "actions": [],
        }
        report["rounds"].append(round_report)

        if first_player.player_id == p2.player_id:
            record_action(
                client,
                p2,
                match_id,
                expected_round,
                {"action": "pass", "action_id": f"{args.challenge_id}-p2-r{expected_round}-first-pass"},
            )
            round_report["actions"].append({"player_id": p2.player_id, "action": "pass"})
            print(f"round {expected_round}: p2 passed from first turn")
            p1_state = wait_for_turn(client, p1, expected_round, args)
        else:
            p1_state = first_state

        card_action = choose_play_card(p1_state)
        play_body = {
            "action": "play_card",
            "card_id": card_action["card_id"],
            "row": first_row(card_action),
            "action_id": f"{args.challenge_id}-p1-r{expected_round}-play",
        }
        record_action(
            client,
            p1,
            match_id,
            expected_round,
            play_body,
        )
        if expected_round == 1 and not args.skip_idempotency_check:
            duplicate_play = record_action(client, p1, match_id, expected_round, play_body)
            expect(duplicate_play.get("duplicate") is True, "duplicate play action was not idempotent")
            report["idempotency_checks"].append(
                {
                    "player_id": p1.player_id,
                    "round_number": expected_round,
                    "action_id": play_body["action_id"],
                    "duplicate": duplicate_play.get("duplicate"),
                }
            )
            add_step(
                report,
                "duplicate_action_verified",
                player_id=p1.player_id,
                round_number=expected_round,
                action_id=play_body["action_id"],
            )
        round_report["actions"].append(
            {
                "player_id": p1.player_id,
                "action": "play_card",
                "card_id": card_action["card_id"],
                "row": first_row(card_action),
            }
        )
        print(f"round {expected_round}: p1 played {card_action['card_id']}")

        if first_player.player_id != p2.player_id:
            wait_for_turn(client, p2, expected_round, args)
            record_action(
                client,
                p2,
                match_id,
                expected_round,
                {"action": "pass", "action_id": f"{args.challenge_id}-p2-r{expected_round}-pass"},
            )
            round_report["actions"].append({"player_id": p2.player_id, "action": "pass"})
            print(f"round {expected_round}: p2 passed")

        wait_for_turn(client, p1, expected_round, args)
        result = record_action(
            client,
            p1,
            match_id,
            expected_round,
            {"action": "pass", "action_id": f"{args.challenge_id}-p1-r{expected_round}-pass"},
        )
        round_report["actions"].append({"player_id": p1.player_id, "action": "pass"})
        print(f"round {expected_round}: p1 passed")

    match_after_rounds = result.get("match") if isinstance(result, dict) else {}
    expect(isinstance(match_after_rounds, dict), "round result did not include match")
    expect(match_after_rounds.get("status") == "awaiting_finish", "match is not awaiting finish")
    expect(match_after_rounds.get("winner_id") == p1.player_id, "p1 did not win the smoke match")
    report["winner_id"] = p1.player_id
    report["pre_finish_match_status"] = match_after_rounds.get("status")
    add_step(report, "rounds_completed", status=match_after_rounds.get("status"), winner_id=p1.player_id)

    finished = client.post(
        f"/api/pvp/matches/{match_id}/finish",
        {"winner_id": p1.player_id, "outcome": "http_smoke", "source": "ios_gwent_http_smoke"},
        player_code=p1.code,
    )
    finished_match = finished.get("match")
    expect(isinstance(finished_match, dict), "finish response did not include match")
    expect(finished_match.get("status") == "finished", "match did not finish")
    expect((finished.get("stake_transfer") or {}).get("status") == "applied", "stake was not applied")
    report["finished_match_status"] = finished_match.get("status")
    report["stake_transfer_status"] = (finished.get("stake_transfer") or {}).get("status")
    p1_final = client.get("/api/pvp/player-state", player_code=p1.code)
    recent = p1_final.get("recent_match")
    expect(isinstance(recent, dict), "p1 final state did not expose recent_match")
    expect(recent.get("match_id") == match_id, "recent_match does not match finished match")
    report["recent_match_id"] = recent.get("match_id")
    add_step(
        report,
        "finished_and_visible",
        match_id=match_id,
        stake_transfer_status=report["stake_transfer_status"],
    )
    print("finished match and verified recent_match")


def run_bot_smoke(
    client: ApiClient,
    player: Player,
    args: argparse.Namespace,
    report: dict[str, Any],
) -> None:
    print(f"Server: {client.base_url}")
    print(f"Bot training player: {player.player_id}")
    if not args.skip_preflight:
        state = preflight_player_clear(client, player)
        add_step(
            report,
            "preflight_clear",
            players=[player.player_id],
            challenge_tokens={player.player_id: state.get("challenge_tokens")},
        )
        print("preflight: selected player has no active PvP state")

    started = client.post(
        "/api/pvp/bot-match",
        ready_payload(args.p1_deck_id),
        player_code=player.code,
    )
    match = started.get("match")
    expect(isinstance(match, dict), "bot start response did not include match")
    match_id = str(match.get("match_id") or "")
    expect(bool(match_id), "bot match has no match_id")
    bot = started.get("bot") if isinstance(started.get("bot"), dict) else {}
    bot_player_id = str(bot.get("player_id") or "")
    expect(bot_player_id == "p_gwent_bot_training", f"unexpected bot player id: {bot_player_id or '-'}")
    report["match_id"] = match_id
    report["bot"] = bot
    verify_selected_deck(match, player, args.p1_deck_id, report)
    add_step(report, "bot_match_started", match_id=match_id, bot_player_id=bot_player_id)
    print(f"started bot match {match_id}")

    first_play_checked = False
    final_state: dict[str, Any] = {}
    for action_index in range(1, args.bot_max_actions + 1):
        state = wait_for_player_or_finished(client, player, match_id, args)
        final_state = state
        recent = state.get("recent_match") if isinstance(state.get("recent_match"), dict) else None
        if recent and recent.get("match_id") == match_id and recent.get("status") == "finished":
            break
        review = bot_terminal_review(state, match_id, bot_player_id)
        if review:
            report["recent_match_id"] = match_id
            report["finished_match_status"] = "needs_master_review"
            report["review_reason"] = review.get("review_reason")
            report["winner_id"] = None
            report["stake_transfer_status"] = "practice_no_stake"
            add_step(
                report,
                "bot_terminal_review",
                match_id=match_id,
                review_reason=review.get("review_reason"),
            )
            print(f"bot match reached terminal review: {review.get('review_reason') or 'needs_master_review'}")
            return

        legal = state.get("legal_actions") if isinstance(state.get("legal_actions"), dict) else {}
        round_number = int(legal.get("round_number") or 1)
        action_body: dict[str, Any]
        card_action = choose_play_card(state) if legal.get("can_play_card") else None
        if card_action is not None:
            action_body = {
                "action": "play_card",
                "card_id": card_action["card_id"],
                "row": first_row(card_action),
                "action_id": f"{args.challenge_id}-bot-human-{action_index}-play",
            }
            target = first_target(card_action)
            if target and card_action.get("target_kind") == "own_non_hero_unit":
                action_body["target_card_id"] = target
            elif target and card_action.get("target_kind") == "graveyard_unit":
                action_body["revive_card_id"] = target
        elif legal.get("can_pass"):
            action_body = {
                "action": "pass",
                "action_id": f"{args.challenge_id}-bot-human-{action_index}-pass",
            }
        else:
            raise SmokeError(f"bot smoke found no legal human action: {short_json(state)}")

        result = record_action(client, player, match_id, round_number, action_body)
        report.setdefault("rounds", []).append(
            {
                "round_number": round_number,
                "actions": [
                    {
                        "player_id": player.player_id,
                        "action": action_body["action"],
                        "card_id": action_body.get("card_id"),
                        "row": action_body.get("row"),
                    }
                ],
            }
        )
        print(f"bot round {round_number}: human {action_body['action']}")

        if action_body["action"] == "play_card" and not first_play_checked and not args.skip_idempotency_check:
            duplicate = record_action(client, player, match_id, round_number, action_body)
            expect(duplicate.get("duplicate") is True, "duplicate bot play action was not idempotent")
            first_play_checked = True
            report["idempotency_checks"].append(
                {
                    "player_id": player.player_id,
                    "round_number": round_number,
                    "action_id": action_body["action_id"],
                    "duplicate": duplicate.get("duplicate"),
                }
            )
            add_step(
                report,
                "duplicate_action_verified",
                player_id=player.player_id,
                round_number=round_number,
                action_id=action_body["action_id"],
            )

        result_match = result.get("match") if isinstance(result.get("match"), dict) else {}
        if result_match.get("status") == "finished":
            final_state = client.get("/api/pvp/player-state", player_code=player.code)
            break
    else:
        raise SmokeError(f"bot match did not finish within {args.bot_max_actions} human actions")

    recent = final_state.get("recent_match") if isinstance(final_state.get("recent_match"), dict) else None
    expect(isinstance(recent, dict), "bot final state did not expose recent_match")
    expect(recent.get("match_id") == match_id, "bot recent_match does not match finished match")
    expect(recent.get("status") == "finished", "bot recent_match is not finished")
    expect(final_state.get("active_match") is None, "bot match still appears as active")
    report["recent_match_id"] = recent.get("match_id")
    report["finished_match_status"] = recent.get("status")
    report["winner_id"] = recent.get("winner_id")
    report["stake_transfer_status"] = "practice_no_stake"
    add_step(report, "bot_finished_and_visible", match_id=match_id, winner_id=recent.get("winner_id"))
    print("finished bot match and verified recent_match")


def bot_terminal_review(
    state: dict[str, Any],
    match_id: str,
    bot_player_id: str,
) -> dict[str, Any] | None:
    for key in ("active_match", "match", "recent_match"):
        value = state.get(key)
        if not isinstance(value, dict) or value.get("status") != "needs_master_review":
            continue
        if value.get("match_id") and value.get("match_id") != match_id:
            continue
        players = {str(value.get("challenger_id") or ""), str(value.get("target_id") or "")}
        if bot_player_id in players or not players.difference({""}):
            return value

    challenge = state.get("active_challenge")
    if not isinstance(challenge, dict) or challenge.get("status") != "needs_master_review":
        return None
    players = {str(challenge.get("challenger_id") or ""), str(challenge.get("target_id") or "")}
    if bot_player_id in players:
        return challenge
    return None


def wait_for_any_turn(
    client: ApiClient,
    players: tuple[Player, ...],
    round_number: int,
    args: argparse.Namespace,
) -> tuple[Player, dict[str, Any]]:
    last_state: dict[str, Any] = {}
    for _ in range(args.poll_attempts):
        for player in players:
            state = client.get("/api/pvp/player-state", player_code=player.code)
            last_state = state
            legal = state.get("legal_actions") if isinstance(state.get("legal_actions"), dict) else {}
            if (
                legal.get("turn_player_id") == player.player_id
                and legal.get("is_player_turn") is True
                and int(legal.get("round_number") or 0) == round_number
            ):
                return player, state
        time.sleep(args.poll_seconds)
    raise SmokeError(f"timed out waiting for any turn in round {round_number}; last_state={short_json(last_state)}")


def wait_for_player_or_finished(
    client: ApiClient,
    player: Player,
    match_id: str,
    args: argparse.Namespace,
) -> dict[str, Any]:
    last_state: dict[str, Any] = {}
    for _ in range(args.poll_attempts):
        state = client.get("/api/pvp/player-state", player_code=player.code)
        last_state = state
        recent = state.get("recent_match") if isinstance(state.get("recent_match"), dict) else None
        if recent and recent.get("match_id") == match_id and recent.get("status") == "finished":
            return state
        active_match = state.get("active_match") if isinstance(state.get("active_match"), dict) else None
        active_challenge = state.get("active_challenge") if isinstance(state.get("active_challenge"), dict) else None
        if (active_match and active_match.get("status") == "needs_master_review") or (
            active_challenge and active_challenge.get("status") == "needs_master_review"
        ):
            return state
        legal = state.get("legal_actions") if isinstance(state.get("legal_actions"), dict) else {}
        if legal.get("is_player_turn") is True and legal.get("turn_player_id") == player.player_id:
            return state
        time.sleep(args.poll_seconds)
    raise SmokeError(f"timed out waiting for player turn or finish; last_state={short_json(last_state)}")


def preflight_player_clear(
    client: ApiClient,
    player: Player,
    *,
    require_challenge_token: bool = False,
) -> dict[str, Any]:
    state = client.get("/api/pvp/player-state", player_code=player.code)
    active_match = state.get("active_match")
    active_challenge = state.get("active_challenge")
    if active_match or active_challenge:
        match_id = ""
        challenge_id = ""
        if isinstance(active_match, dict):
            match_id = str(active_match.get("match_id") or "")
            challenge_id = str(active_match.get("challenge_id") or "")
        if isinstance(active_challenge, dict):
            challenge_id = str(active_challenge.get("challenge_id") or challenge_id)
        raise SmokeError(
            "selected player already has active PvP state: "
            f"{player.player_id} match={match_id or '-'} challenge={challenge_id or '-'}"
        )
    if require_challenge_token:
        raw_tokens = state.get("challenge_tokens")
        if raw_tokens is None:
            raise SmokeError(
                "player-state did not include challenge_tokens; restart the FastAPI server from "
                "the current iOS Gwent branch"
            )
        try:
            challenge_tokens = int(raw_tokens)
        except (TypeError, ValueError) as exc:
            raise SmokeError(f"invalid challenge_tokens for {player.player_id}: {raw_tokens!r}") from exc
        if challenge_tokens <= 0:
            raise SmokeError(
                f"selected challenger has no challenge tokens: {player.player_id}; "
                "start Act 1 through the master API/Admin Studio before running PvP smoke"
            )
    return state


def verify_snapshot_for_player(
    snapshot: dict[str, Any],
    player: Player,
    expected_deck_id: str,
    report: dict[str, Any],
) -> None:
    expect(bool(snapshot.get("snapshot_version")), "snapshot has no snapshot_version")
    auth = snapshot.get("auth") if isinstance(snapshot.get("auth"), dict) else {}
    scoped_player = snapshot.get("player") if isinstance(snapshot.get("player"), dict) else {}
    actual_player_id = str(auth.get("player_id") or scoped_player.get("player_id") or "")
    expect(
        actual_player_id == player.player_id,
        f"snapshot player mismatch for {player.player_id}: got {actual_player_id or '-'}",
    )
    gwent_cards = snapshot.get("gwent_cards")
    gwent_decks = snapshot.get("gwent_decks")
    expect(isinstance(gwent_cards, list) and bool(gwent_cards), "snapshot has no gwent_cards")
    expect(isinstance(gwent_decks, list) and bool(gwent_decks), "snapshot has no gwent_decks")
    player_decks = [
        deck
        for deck in gwent_decks
        if isinstance(deck, dict) and str(deck.get("player_id") or "") == player.player_id
    ]
    expect(player_decks, f"snapshot has no Gwent deck for {player.player_id}")
    normalized_deck_id = expected_deck_id.strip()
    if normalized_deck_id:
        deck_ids = {str(deck.get("deck_id") or "") for deck in player_decks}
        expect(
            normalized_deck_id in deck_ids,
            f"snapshot deck mismatch for {player.player_id}: {normalized_deck_id} is not visible",
        )
    report.setdefault("snapshots", {})[player.player_id] = {
        "snapshot_version": snapshot.get("snapshot_version"),
        "deck_count": len(player_decks),
        "selected_deck_id": normalized_deck_id or None,
    }


def ready_payload(deck_id: str, preferred_starting_player_id: str = "") -> dict[str, Any]:
    payload: dict[str, Any] = {"mulligans": [], "source": "ios_gwent_http_smoke"}
    normalized_deck_id = deck_id.strip()
    if normalized_deck_id:
        payload["deck_id"] = normalized_deck_id
    normalized_starting_player_id = preferred_starting_player_id.strip()
    if normalized_starting_player_id:
        payload["preferred_starting_player_id"] = normalized_starting_player_id
    return payload


def verify_selected_deck(
    match: dict[str, Any],
    player: Player,
    expected_deck_id: str,
    report: dict[str, Any],
) -> None:
    normalized_deck_id = expected_deck_id.strip()
    if not normalized_deck_id:
        return
    deck_state = match.get("deck_state") if isinstance(match.get("deck_state"), dict) else {}
    player_deck = deck_state.get(player.player_id) if isinstance(deck_state, dict) else {}
    expect(isinstance(player_deck, dict), f"match has no deck state for {player.player_id}")
    actual_deck_id = str(player_deck.get("deck_id") or "")
    expect(
        actual_deck_id == normalized_deck_id,
        f"selected deck mismatch for {player.player_id}: expected {normalized_deck_id}, got {actual_deck_id or '-'}",
    )
    report.setdefault("decks", {})[player.player_id] = {
        "deck_id": actual_deck_id,
        "faction": player_deck.get("faction"),
    }
    add_step(
        report,
        "deck_verified",
        player_id=player.player_id,
        deck_id=actual_deck_id,
        faction=player_deck.get("faction"),
    )


def verify_selected_starting_player(
    match: dict[str, Any],
    expected_starting_player_id: str,
    report: dict[str, Any],
) -> None:
    normalized_expected = expected_starting_player_id.strip()
    if not normalized_expected:
        return
    deck_state = match.get("deck_state") if isinstance(match.get("deck_state"), dict) else {}
    active_round = deck_state.get("active_round") if isinstance(deck_state, dict) else {}
    expect(isinstance(active_round, dict), "match has no active_round in deck_state")
    actual_starting_player_id = str(active_round.get("starting_player_id") or "")
    actual_turn_player_id = str(active_round.get("turn_player_id") or "")
    expect(
        actual_starting_player_id == normalized_expected,
        "selected starting player mismatch: "
        f"expected {normalized_expected}, got {actual_starting_player_id or '-'}",
    )
    expect(
        actual_turn_player_id == normalized_expected,
        "selected turn player mismatch: "
        f"expected {normalized_expected}, got {actual_turn_player_id or '-'}",
    )
    report["starting_player_id"] = actual_starting_player_id
    add_step(report, "starting_player_verified", player_id=actual_starting_player_id)


def wait_for_turn(
    client: ApiClient,
    player: Player,
    round_number: int,
    args: argparse.Namespace,
) -> dict[str, Any]:
    last_state: dict[str, Any] = {}
    for _ in range(args.poll_attempts):
        state = client.get("/api/pvp/player-state", player_code=player.code)
        last_state = state
        legal = state.get("legal_actions") if isinstance(state.get("legal_actions"), dict) else {}
        if (
            legal.get("turn_player_id") == player.player_id
            and legal.get("is_player_turn") is True
            and int(legal.get("round_number") or 0) == round_number
        ):
            return state
        time.sleep(args.poll_seconds)
    raise SmokeError(f"timed out waiting for {player.player_id} turn; last_state={short_json(last_state)}")


def record_action(
    client: ApiClient,
    player: Player,
    match_id: str,
    round_number: int,
    action: dict[str, Any],
) -> dict[str, Any]:
    body = {"round_number": round_number, "source": "ios_gwent_http_smoke", **action}
    return client.post(f"/api/pvp/matches/{match_id}/actions", body, player_code=player.code)


def choose_play_card(state: dict[str, Any]) -> dict[str, Any] | None:
    legal = state.get("legal_actions") if isinstance(state.get("legal_actions"), dict) else {}
    cards = legal.get("playable_cards") if isinstance(legal.get("playable_cards"), list) else []
    for action in cards:
        if not isinstance(action, dict):
            continue
        if action.get("type") == "unit" and action.get("effect") != "spy" and first_row(action):
            return action
    for action in cards:
        if isinstance(action, dict) and first_row(action):
            return action
    for action in cards:
        if not isinstance(action, dict):
            continue
        if action.get("requires_target") and not action.get("targets"):
            continue
        return action
    return None


def first_row(action: dict[str, Any]) -> str:
    rows = action.get("allowed_rows")
    if isinstance(rows, list) and rows:
        return str(rows[0])
    return ""


def first_target(action: dict[str, Any]) -> str:
    targets = action.get("targets")
    if not isinstance(targets, list) or not targets:
        return ""
    target = targets[0]
    if isinstance(target, dict):
        return str(target.get("card_id") or "")
    return ""


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise SmokeError(message)


def add_step(report: dict[str, Any], name: str, **fields: Any) -> None:
    report.setdefault("steps", []).append({"name": name, "at": int(time.time()), **fields})


def write_json_report(path: str | None, report: dict[str, Any]) -> None:
    if not path:
        return
    target = Path(path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(f"report: {target}")


def short_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)[:800]


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
