import json
from typing import Any, Dict, List


class MatchCache:
    def __init__(self, path: str):
        self.path = path
        self.data = self._load()

    def _load(self) -> Dict[str, Any]:
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except FileNotFoundError:
            raw = {"version": 1, "matches": {}}
        except json.JSONDecodeError:
            raw = {"version": 1, "matches": {}}

        if not isinstance(raw, dict):
            raw = {"version": 1, "matches": {}}
        matches = raw.get("matches")
        if not isinstance(matches, dict):
            raw["matches"] = {}
        raw["version"] = 1
        return raw

    @property
    def matches(self) -> Dict[str, Any]:
        return self.data.setdefault("matches", {})

    def save(self) -> None:
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)

    def get_match(self, match_id: str) -> Dict[str, Any]:
        item = self.matches.get(match_id)
        return item if isinstance(item, dict) else {}

    def upsert_match(self, match_id: str, payload: Dict[str, Any]) -> None:
        self.matches[match_id] = payload

    def _build_record(self, match_id: str, item: Dict[str, Any], player_names: List[str], allowed: set[str]) -> Dict[str, Any] | None:
        if not isinstance(item, dict):
            return None
        if item.get("usable") is False:
            return None
        mode = str(item.get("game_mode", ""))
        if mode not in allowed:
            return None
        players = item.get("players", {})
        if not isinstance(players, dict):
            return None
        if not all(name in players for name in player_names):
            return None

        kills: Dict[str, float] = {}
        for name in player_names:
            p = players.get(name)
            if not isinstance(p, dict) or "kills" not in p:
                return None
            kills[name] = float(p.get("kills", 0))

        return {
            "match_id": match_id,
            "created_at": str(item.get("created_at", "")),
            "kills": kills,
        }

    def find_common_records(self, player_names: List[str], limit: int, allowed_modes: List[str]) -> List[Dict[str, Any]]:
        allowed = set(allowed_modes)
        records: List[Dict[str, Any]] = []

        for match_id, item in self.matches.items():
            record = self._build_record(match_id, item, player_names, allowed)
            if record is not None:
                records.append(record)

        records.sort(key=lambda x: x["created_at"], reverse=True)
        return records[:limit]

    def find_records_by_match_ids(
        self,
        match_ids: List[str],
        player_names: List[str],
        limit: int,
        allowed_modes: List[str],
    ) -> List[Dict[str, Any]]:
        allowed = set(allowed_modes)
        records: List[Dict[str, Any]] = []
        seen = set()

        for match_id in match_ids:
            if match_id in seen:
                continue
            seen.add(match_id)
            record = self._build_record(match_id, self.get_match(match_id), player_names, allowed)
            if record is not None:
                records.append(record)
            if len(records) >= limit:
                break

        return records

    def player_global_avg(self, player_name: str, allowed_modes: List[str]) -> Dict[str, float]:
        allowed = set(allowed_modes)
        total = 0.0
        count = 0
        for item in self.matches.values():
            if not isinstance(item, dict):
                continue
            if item.get("usable") is False:
                continue
            mode = str(item.get("game_mode", ""))
            if mode not in allowed:
                continue
            players = item.get("players", {})
            if not isinstance(players, dict):
                continue
            p = players.get(player_name)
            if not isinstance(p, dict) or "kills" not in p:
                continue
            total += float(p.get("kills", 0))
            count += 1

        return {
            "avg": (total / count) if count > 0 else 0.0,
            "count": float(count),
        }
