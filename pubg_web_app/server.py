from __future__ import annotations

from flask import Flask, jsonify, render_template, request

from pubg_cli_app.api import PubgAPIError
from pubg_cli_app.config import ConfigError, add_player_to_config, load_config
from pubg_web_app.service import analyze_settlement


def create_app(config_path: str = "config.json") -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")

    try:
        initial_config = load_config(config_path)
    except (ConfigError, FileNotFoundError, ValueError) as exc:
        raise RuntimeError(f"配置加载失败: {exc}") from exc

    state = {"config": initial_config}

    def current_config():
        return state["config"]

    def current_player_names():
        return [p.name for p in current_config().players]

    @app.get("/")
    def index() -> str:
        config = current_config()
        return render_template(
            "index.html",
            players=current_player_names(),
            target_matches=config.num_matches,
            platform=config.platform,
        )

    @app.get("/api/meta")
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

    @app.post("/api/players")
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

    @app.post("/api/analyze")
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
