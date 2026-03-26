import argparse
import sys

from pubg_cli_app.app import run_cli
from pubg_cli_app.config import ConfigError, load_config
from pubg_cli_app.console import error


def main() -> int:
    parser = argparse.ArgumentParser(description="PUBG 历史均分结算 CLI")
    parser.add_argument("--config", default="config.json", help="配置文件路径")
    parser.add_argument(
        "--no-refresh",
        action="store_true",
        help="不在线拉取新数据，仅使用 CLI 自己的本地缓存",
    )
    args = parser.parse_args()

    try:
        config = load_config(args.config)
    except (ConfigError, FileNotFoundError, ValueError) as exc:
        print(error(f"配置加载失败: {exc}"))
        return 1

    return run_cli(config, no_refresh=args.no_refresh)


if __name__ == "__main__":
    sys.exit(main())
