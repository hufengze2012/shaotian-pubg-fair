from __future__ import annotations

from typing import Any, Dict, List

from pubg_cli_app.api import PubgClient
from pubg_cli_app.cache import MatchCache
from pubg_cli_app.config import AppConfig
from pubg_cli_app.history import build_kill_profile, load_common_records, refresh_common_history
from pubg_cli_app.scoring import (
    evaluate_individual,
    evaluate_team,
    suggest_individual_handicaps,
    suggest_team_handicaps,
)


def _to_float(value: Any, field_name: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} 必须是数字") from exc


def _validate_half_step(value: float, field_name: str) -> float:
    if value < 0:
        raise ValueError(f"{field_name} 必须 >= 0")
    if abs(value * 2 - round(value * 2)) > 1e-9:
        raise ValueError(f"{field_name} 必须是 0.5 的倍数")
    return round(value, 2)


def _validate_selected_players(payload: Dict[str, Any], all_players: List[str]) -> List[str]:
    selected = payload.get("selected_names", [])
    if not isinstance(selected, list):
        raise ValueError("selected_names 格式错误")
    selected_names = [str(x).strip() for x in selected if str(x).strip()]
    if len(selected_names) != 4:
        raise ValueError("必须且仅能选择 4 名玩家")
    if len(set(selected_names)) != 4:
        raise ValueError("玩家选择不能重复")
    invalid = [name for name in selected_names if name not in all_players]
    if invalid:
        raise ValueError(f"存在无效玩家: {invalid}")
    return selected_names


def _validate_individual_handicaps(payload: Dict[str, Any], selected_names: List[str]) -> Dict[str, float]:
    raw = payload.get("individual_handicaps", {})
    if not isinstance(raw, dict):
        raise ValueError("individual_handicaps 格式错误")
    handicaps: Dict[str, float] = {}
    for name in selected_names:
        if name not in raw:
            raise ValueError(f"缺少 {name} 的个人让分")
        val = _to_float(raw.get(name), f"{name} 个人让分")
        handicaps[name] = _validate_half_step(val, f"{name} 个人让分")
    return handicaps


def _validate_team_inputs(payload: Dict[str, Any], selected_names: List[str]) -> Dict[str, Any]:
    team_a_raw = payload.get("team_a", [])
    if not isinstance(team_a_raw, list):
        raise ValueError("team_a 格式错误")
    team_a = [str(x).strip() for x in team_a_raw if str(x).strip()]
    if len(team_a) != 2:
        raise ValueError("A队必须选择 2 名玩家")
    if len(set(team_a)) != 2:
        raise ValueError("A队成员不能重复")
    if any(name not in selected_names for name in team_a):
        raise ValueError("A队成员必须来自已选 4 名玩家")

    team_b = [name for name in selected_names if name not in team_a]
    if len(team_b) != 2:
        raise ValueError("B队成员计算失败，请重新选择分队")

    h_a = _validate_half_step(_to_float(payload.get("team_handicap_a", 0), "A队让分"), "A队让分")
    h_b = _validate_half_step(_to_float(payload.get("team_handicap_b", 0), "B队让分"), "B队让分")
    if h_a > 0 and h_b > 0:
        raise ValueError("组队规则限制：A队和B队不能同时 > 0")

    return {"team_a": team_a, "team_b": team_b, "team_handicaps": {"A": h_a, "B": h_b}}


def _format_profile(selected_names: List[str], profile: Dict[str, Dict[str, float]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for name in selected_names:
        item = profile[name]
        rows.append(
            {
                "name": name,
                "global_avg": float(item["global_avg"]),
                "global_count": int(item["global_count"]),
                "together_avg": float(item["together_avg"]),
                "together_count": int(item["together_count"]),
            }
        )
    return rows


def _format_refresh_stats(stats: Any) -> Dict[str, Any] | None:
    if stats is None:
        return None
    return {
        "shard": stats.shard,
        "common_candidates": stats.common_candidates,
        "cache_hits": stats.cache_hits,
        "detail_requests": stats.detail_requests,
        "player_match_counts": dict(stats.player_match_counts),
        "pair_overlaps": dict(stats.pair_overlaps),
    }


def analyze_settlement(config: AppConfig, payload: Dict[str, Any]) -> Dict[str, Any]:
    all_players = [player.name for player in config.players]
    selected_names = _validate_selected_players(payload, all_players)

    mode = str(payload.get("mode", "individual")).strip().lower()
    if mode not in {"individual", "team"}:
        raise ValueError("mode 仅支持 individual 或 team")

    refresh = bool(payload.get("refresh", True))
    cache = MatchCache(config.cache_path)
    refresh_stats = None

    if refresh:
        client = PubgClient(
            api_key=config.api_key,
            timeout=config.request_timeout,
            max_retries=config.max_retries,
        )
        refresh_stats = refresh_common_history(
            client=client,
            cache=cache,
            platform=config.platform,
            names=selected_names,
        )

    if refresh_stats is not None:
        records = load_common_records(
            cache,
            selected_names,
            config.num_matches,
            refresh_stats.common_match_ids,
        )
    else:
        records = load_common_records(cache, selected_names, config.num_matches)
    refresh_payload = _format_refresh_stats(refresh_stats)

    if not records:
        diagnostics = None
        if refresh_payload is not None and refresh_payload["common_candidates"] == 0:
            diagnostics = {
                "reason": "当前查询窗口内四人同局交集为空",
                "player_match_counts": refresh_payload["player_match_counts"],
                "pair_overlaps": refresh_payload["pair_overlaps"],
            }
        return {
            "ok": False,
            "error": "没有找到这4个人同局的历史数据。请检查玩家组合或开启在线刷新重试。",
            "selected_names": selected_names,
            "refresh": refresh_payload,
            "diagnostics": diagnostics,
        }

    profile = build_kill_profile(cache, selected_names, records)
    profile_rows = _format_profile(selected_names, profile)

    if mode == "individual":
        manual_handicaps = _validate_individual_handicaps(payload, selected_names)
        manual_eval = evaluate_individual(records, selected_names, manual_handicaps)
        suggestion = suggest_individual_handicaps(records, selected_names)
        return {
            "ok": True,
            "mode": "individual",
            "selected_names": selected_names,
            "meta": {"sample_count": len(records), "target_matches": config.num_matches},
            "refresh": refresh_payload,
            "profile": profile_rows,
            "manual": {"handicaps": manual_handicaps, "evaluation": manual_eval},
            "suggestion": {
                "handicaps": suggestion["handicaps"],
                "evaluation": suggestion["evaluation"],
            },
        }

    team_inputs = _validate_team_inputs(payload, selected_names)
    team_a = team_inputs["team_a"]
    team_b = team_inputs["team_b"]
    team_handicaps = team_inputs["team_handicaps"]
    manual_eval = evaluate_team(records, selected_names, team_a, team_b, team_handicaps)
    suggestion = suggest_team_handicaps(records, selected_names, team_a, team_b)

    return {
        "ok": True,
        "mode": "team",
        "selected_names": selected_names,
        "meta": {"sample_count": len(records), "target_matches": config.num_matches},
        "refresh": refresh_payload,
        "profile": profile_rows,
        "team": {"A": team_a, "B": team_b},
        "manual": {"handicaps": team_handicaps, "evaluation": manual_eval},
        "suggestion": {
            "handicaps": suggestion["handicaps"],
            "evaluation": suggestion["evaluation"],
        },
    }
