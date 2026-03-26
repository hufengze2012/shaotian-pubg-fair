from time import sleep
from typing import Any, Dict, List, Tuple

import requests


class PubgAPIError(Exception):
    pass


class PubgClient:
    def __init__(self, api_key: str, timeout: int = 8, max_retries: int = 3):
        self.timeout = timeout
        self.max_retries = max_retries
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/vnd.api+json",
            "Accept-Encoding": "gzip",
        }

    def _request_json(self, url: str) -> Dict[str, Any]:
        last_err: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                resp = requests.get(url, headers=self.headers, timeout=self.timeout)
            except requests.RequestException as exc:
                last_err = exc
                if attempt < self.max_retries - 1:
                    sleep(1 + attempt)
                    continue
                raise PubgAPIError(f"请求失败: {url} | 错误: {exc}") from exc

            if resp.status_code == 200:
                return resp.json()

            if resp.status_code == 429 and attempt < self.max_retries - 1:
                retry_after = resp.headers.get("Retry-After")
                wait_seconds = int(retry_after) if retry_after and retry_after.isdigit() else (2 + attempt)
                sleep(wait_seconds)
                continue

            raise PubgAPIError(
                f"请求失败: {url} | 状态码: {resp.status_code} | 响应: {resp.text[:200]}"
            )

        raise PubgAPIError(f"请求失败: {url} | 最后错误: {last_err}")

    def lookup_players(self, shard: str, names: List[str]) -> Tuple[Dict[str, str], Dict[str, List[str]]]:
        if len(names) > 10:
            raise PubgAPIError("players 查询单次最多支持 10 个玩家")

        url = f"https://api.pubg.com/shards/{shard}/players?filter[playerNames]={','.join(names)}"
        payload = self._request_json(url)
        account_map: Dict[str, str] = {}
        match_map: Dict[str, List[str]] = {}

        for item in payload.get("data", []):
            name = item.get("attributes", {}).get("name")
            account_id = item.get("id")
            if not name or not account_id:
                continue

            relations = item.get("relationships", {})
            matches = relations.get("matches", {}).get("data", [])
            match_ids = [m.get("id") for m in matches if m.get("type") == "match" and m.get("id")]

            account_map[name] = account_id
            match_map[name] = match_ids

        return account_map, match_map

    def get_match(self, shard: str, match_id: str) -> Dict[str, Any]:
        url = f"https://api.pubg.com/shards/{shard}/matches/{match_id}"
        return self._request_json(url)
