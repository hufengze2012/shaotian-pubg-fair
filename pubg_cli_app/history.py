from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from pubg_cli_app.api import PubgAPIError, PubgClient
from pubg_cli_app.cache import MatchCache


ALLOWED_MODES = ["squad", "normal-squad", "squad-tpp"]


@dataclass
class RefreshStats:
    shard: str
    common_candidates: int
    cache_hits: int
    detail_requests: int
    player_match_counts: Dict[str, int]
    pair_overlaps: Dict[str, int]
    common_match_ids: List[str]


def _all_empty_match_lists(match_map: Dict[str, List[str]], names: List[str]) -> bool:
    if not match_map:
        return False
    return all(len(match_map.get(name, [])) == 0 for name in names)


def lookup_with_fallback(
    client: PubgClient,
    platform: str,
    names: List[str],
) -> Tuple[str, Dict[str, str], Dict[str, List[str]]]:
    account_map, match_map = client.lookup_players(platform, names)

    if platform.startswith("pc-") and _all_empty_match_lists(match_map, names):
        steam_accounts, steam_matches = client.lookup_players("steam", names)
        if steam_accounts:
            return "steam", steam_accounts, steam_matches

    return platform, account_map, match_map


def _common_match_ids_ordered(match_map: Dict[str, List[str]], names: List[str]) -> List[str]:
    if not names:
        return []

    first = match_map.get(names[0], [])
    others = [set(match_map.get(name, [])) for name in names[1:]]
    result: List[str] = []
    seen = set()

    for match_id in first:
        if match_id in seen:
            continue
        if all(match_id in group for group in others):
            result.append(match_id)
            seen.add(match_id)

    return result


def _pair_overlaps(match_map: Dict[str, List[str]], names: List[str]) -> Dict[str, int]:
    result: Dict[str, int] = {}
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a = names[i]
            b = names[j]
            sa = set(match_map.get(a, []))
            sb = set(match_map.get(b, []))
            result[f"{a} & {b}"] = len(sa & sb)
    return result


def _build_match_payload(shard: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    mode = str(payload.get("data", {}).get("attributes", {}).get("gameMode", ""))
    created_at = str(payload.get("data", {}).get("attributes", {}).get("createdAt", ""))

    players: Dict[str, Any] = {}
    for item in payload.get("included", []):
        if item.get("type") != "participant":
            continue
        stats = item.get("attributes", {}).get("stats", {})
        name = stats.get("name")
        if not name:
            continue
        players[name] = {"kills": int(stats.get("kills", 0))}

    return {
        "platform": shard,
        "created_at": created_at,
        "game_mode": mode,
        "usable": mode in ALLOWED_MODES,
        "players": players,
    }


def _cache_has_all_players(cache_item: Dict[str, Any], names: List[str]) -> bool:
    players = cache_item.get("players", {}) if isinstance(cache_item, dict) else {}
    if not isinstance(players, dict):
        return False
    return all(name in players for name in names)


def refresh_common_history(
    client: PubgClient,
    cache: MatchCache,
    platform: str,
    names: List[str],
) -> RefreshStats:
    shard, account_map, match_map = lookup_with_fallback(client, platform, names)

    missing = [name for name in names if name not in account_map]
    if missing:
        raise PubgAPIError(f"以下玩家未找到: {missing}")

    common_ids = _common_match_ids_ordered(match_map, names)
    match_counts = {name: len(match_map.get(name, [])) for name in names}
    pair_overlaps = _pair_overlaps(match_map, names)
    cache_hits = 0
    detail_requests = 0

    for match_id in common_ids:
        existing = cache.get_match(match_id)
        if existing and _cache_has_all_players(existing, names):
            cache_hits += 1
            continue

        payload = client.get_match(shard, match_id)
        match_payload = _build_match_payload(shard, payload)
        cache.upsert_match(match_id, match_payload)
        detail_requests += 1

    cache.save()
    return RefreshStats(
        shard=shard,
        common_candidates=len(common_ids),
        cache_hits=cache_hits,
        detail_requests=detail_requests,
        player_match_counts=match_counts,
        pair_overlaps=pair_overlaps,
        common_match_ids=common_ids,
    )


def load_common_records(
    cache: MatchCache,
    names: List[str],
    limit: int,
    match_ids: List[str] | None = None,
) -> List[Dict[str, Any]]:
    if match_ids is not None:
        return cache.find_records_by_match_ids(match_ids, names, limit, ALLOWED_MODES)
    return cache.find_common_records(names, limit, ALLOWED_MODES)


def build_kill_profile(
    cache: MatchCache,
    names: List[str],
    common_records: List[Dict[str, Any]],
) -> Dict[str, Dict[str, float]]:
    together_total = {name: 0.0 for name in names}
    for rec in common_records:
        for name in names:
            together_total[name] += float(rec["kills"][name])

    together_count = len(common_records)
    profile: Dict[str, Dict[str, float]] = {}

    for name in names:
        global_row = cache.player_global_avg(name, ALLOWED_MODES)
        profile[name] = {
            "global_avg": float(global_row["avg"]),
            "global_count": float(global_row["count"]),
            "together_avg": (together_total[name] / together_count) if together_count > 0 else 0.0,
            "together_count": float(together_count),
        }

    return profile
