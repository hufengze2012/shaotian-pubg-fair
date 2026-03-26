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


def _read_raw_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    if not isinstance(raw, dict):
        raise ConfigError("配置文件格式错误")
    return raw


def load_config(path: str) -> AppConfig:
    raw = _read_raw_config(path)

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


def add_player_to_config(path: str, player_name: str) -> AppConfig:
    name = str(player_name).strip()
    if not name:
        raise ConfigError("用户名不能为空")

    raw = _read_raw_config(path)
    players_raw = raw.get("players", [])
    if not isinstance(players_raw, list):
        raise ConfigError("配置中的 players 格式错误")

    existing_names = {
        str(item.get("name", "")).strip().casefold()
        for item in players_raw
        if isinstance(item, dict)
    }
    if name.casefold() in existing_names:
        raise ConfigError(f"用户已存在: {name}")

    platform = str(raw.get("platform", "pc-as")).strip() or "pc-as"
    players_raw.append(
        {
            "name": name,
            "account_id": name,
            "platform": platform,
        }
    )
    raw["players"] = players_raw

    with open(path, "w", encoding="utf-8") as f:
        json.dump(raw, f, indent=2, ensure_ascii=False)
        f.write("\n")

    return load_config(path)
