from __future__ import annotations

from flask import Flask, jsonify, render_template, request

from pubg_cli_app.api import PubgAPIError
from pubg_cli_app.config import ConfigError, add_player_to_config, load_config
from pubg_web_app.service import analyze_settlement


def normalize_base_path(base_path: str) -> str:
    value = str(base_path or "").strip()
    if not value or value == "/":
        return ""
    if not value.startswith("/"):
        value = f"/{value}"
    return value.rstrip("/")


def create_app(config_path: str = "config.json", base_path: str = "/pubg") -> Flask:
    normalized_base_path = normalize_base_path(base_path)
    index_path = f"{normalized_base_path}/" if normalized_base_path else "/"
    meta_path = f"{normalized_base_path}/api/meta" if normalized_base_path else "/api/meta"
    add_player_path = f"{normalized_base_path}/api/players" if normalized_base_path else "/api/players"
    analyze_path = f"{normalized_base_path}/api/analyze" if normalized_base_path else "/api/analyze"
    static_url_path = f"{normalized_base_path}/static" if normalized_base_path else "/static"
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
        static_url_path=static_url_path,
    )

    try:
        initial_config = load_config(config_path)
    except (ConfigError, FileNotFoundError, ValueError) as exc:
        raise RuntimeError(f"配置加载失败: {exc}") from exc

    state = {"config": initial_config}

    def current_config():
        return state["config"]

    def current_player_names():
        return [p.name for p in current_config().players]

    if normalized_base_path:

        @app.get("/")
        def root():
            return f"请通过 {normalized_base_path}/ 访问。", 404

    @app.get(index_path)
    def index() -> str:
        config = current_config()
        return render_template(
            "index.html",
            players=current_player_names(),
            target_matches=config.num_matches,
            platform=config.platform,
            base_path=normalized_base_path,
        )

    @app.get(meta_path)
    def meta():
        config = current_config()
        return jsonify(
            {
                "players": current_player_names(),
                "target_matches": config.num_matches,
                "platform": config.platform,
                "cache_path": config.cache_path,
            }
        )

    @app.post(add_player_path)
    def add_player():
        payload = request.get_json(silent=True) or {}
        try:
            name = str(payload.get("name", "")).strip()
            if not name:
                raise ValueError("用户名不能为空")
            state["config"] = add_player_to_config(config_path, name)
            return jsonify(
                {
                    "ok": True,
                    "name": name,
                    "players": current_player_names(),
                }
            )
        except (ValueError, ConfigError) as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400

    @app.post(analyze_path)
    def analyze():
        payload = request.get_json(silent=True) or {}
        try:
            result = analyze_settlement(current_config(), payload)
            return jsonify(result)
        except (ValueError, PubgAPIError) as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        except Exception:
            return jsonify({"ok": False, "error": "服务器内部错误，请查看后端日志"}), 500

    return app
