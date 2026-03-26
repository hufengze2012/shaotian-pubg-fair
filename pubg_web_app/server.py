from __future__ import annotations

from flask import Flask, jsonify, render_template, request

from pubg_cli_app.api import PubgAPIError
from pubg_cli_app.config import ConfigError, load_config
from pubg_web_app.service import analyze_settlement


def create_app(config_path: str = "config.json") -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")

    try:
        config = load_config(config_path)
    except (ConfigError, FileNotFoundError, ValueError) as exc:
        raise RuntimeError(f"配置加载失败: {exc}") from exc

    player_names = [p.name for p in config.players]

    @app.get("/")
    def index() -> str:
        return render_template(
            "index.html",
            players=player_names,
            target_matches=config.num_matches,
            platform=config.platform,
        )

    @app.get("/api/meta")
    def meta():
        return jsonify(
            {
                "players": player_names,
                "target_matches": config.num_matches,
                "platform": config.platform,
                "cache_path": config.cache_path,
            }
        )

    @app.post("/api/analyze")
    def analyze():
        payload = request.get_json(silent=True) or {}
        try:
            result = analyze_settlement(config, payload)
            return jsonify(result)
        except (ValueError, PubgAPIError) as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        except Exception:
            return jsonify({"ok": False, "error": "服务器内部错误，请查看后端日志"}), 500

    return app
