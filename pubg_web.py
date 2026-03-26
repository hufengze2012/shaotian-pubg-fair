import argparse

from pubg_web_app import create_app


def main() -> None:
    parser = argparse.ArgumentParser(description="PUBG 历史均分结算 Web 应用")
    parser.add_argument("--config", default="config.json", help="配置文件路径")
    parser.add_argument("--host", default="127.0.0.1", help="监听地址")
    parser.add_argument("--port", type=int, default=8000, help="监听端口")
    parser.add_argument("--debug", action="store_true", help="开启调试模式")
    args = parser.parse_args()

    app = create_app(args.config)
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
