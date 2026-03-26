import json
from dataclasses import dataclass
from typing import List


@dataclass
class PlayerConfig:
    name: str


@dataclass
class AppConfig:
    players: List[PlayerConfig]
    api_key: str
    platform: str
    num_matches: int
    request_timeout: int
    max_retries: int
    cache_path: str


class ConfigError(Exception):
    pass


def load_config(path: str) -> AppConfig:
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    players_raw = raw.get("players", [])
    players: List[PlayerConfig] = []
    for item in players_raw:
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        players.append(PlayerConfig(name=name))

    if len(players) < 4:
        raise ConfigError("配置中的玩家少于4人")

    api_key = str(raw.get("api_key", "")).strip()
    if not api_key:
        raise ConfigError("未配置 api_key")

    return AppConfig(
        players=players,
        api_key=api_key,
        platform=str(raw.get("platform", "pc-as")),
        num_matches=int(raw.get("num_matches", 100)),
        request_timeout=int(raw.get("request_timeout", 8)),
        max_retries=int(raw.get("max_retries", 3)),
        cache_path=str(raw.get("cli_cache_path", "pubg_cli_cache.json")),
    )
