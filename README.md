# PUBG蜻蜓队长

PUBG 历史均分结算与让分推荐系统。基于玩家历史比赛数据，计算公平的让分方案，让不同水平的玩家在组队竞技中获得均衡的体验。

## 功能特性

- **灵活人数**：支持 2-4 人参赛
- **个人模式**：为每位玩家单独设置让分，系统按有效击杀（原始击杀 - 让分）评估公平性
- **组队模式**：自由分队（2人可 1v1，3人可 1v2，4人可 1v3 或 2v2），按队伍总击杀差计分
- **自动推荐**：根据历史数据自动计算最优让分方案，最小化方差和分差
- **数据拉取**：通过 PUBG 官方 API 获取最新比赛数据，本地缓存加速

## 环境要求

- Python 3.10+
- PUBG 开发者 API Key（从 [PUBG Developer Portal](https://developer.pubg.com/) 获取）

## 安装

```bash
pip install -r requirements.txt
```

## 配置

编辑 `config.json`：

```json
{
  "players": [
    {"name": "玩家A", "account_id": "玩家A", "platform": "pc-as"},
    {"name": "玩家B", "account_id": "玩家B", "platform": "pc-as"}
  ],
  "api_key": "你的PUBG API Key",
  "num_matches": 100,
  "platform": "pc-as"
}
```

| 字段 | 说明 | 默认值 |
|------|------|--------|
| `players` | 玩家列表，至少 2 人 | — |
| `api_key` | PUBG API Bearer Token | — |
| `platform` | 平台分片（`pc-as`、`pc-na` 等） | `pc-as` |
| `num_matches` | 分析的最近比赛上限 | `100` |
| `request_timeout` | API 请求超时（秒） | `8` |
| `max_retries` | API 请求重试次数 | `3` |
| `cli_cache_path` | 缓存文件路径 | `pubg_cli_cache.json` |

## 启动

```bash
python pubg_web.py [--config config.json] [--host 127.0.0.1] [--port 8000] [--debug]
```

浏览器打开 `http://127.0.0.1:8000` 即可使用。

## 使用指南

1. **选择玩家**：从已配置的玩家列表中勾选 2-4 名参赛玩家。可通过"增加用户"按钮添加新玩家
2. **选择模式**：
   - **个人模式**：为每个玩家设置让分值（0.5 步进）
   - **组队模式**：勾选 A 队成员（至少 1 人），B 队自动为其余玩家，分别设置队伍让分
3. **在线刷新**：开启后会从 PUBG API 拉取最新比赛数据
4. **点击"刷新并结算"**：系统输出当前让分评估结果和推荐让分方案

## 让分系统说明

### 基本规则

- 让分步进为 **0.5**，取值 >= 0
- 有效击杀 = max(0, 原始击杀 - 让分)
- 组队模式约束：**A 队和 B 队不能同时让分**（只有强队让分）

### 个人模式

每位玩家的有效击杀 = 原始击杀 - 个人让分。系统统计每人的总分和均分，计算分差（最高 - 最低均分）和方差。

### 组队模式

每场比赛中，队伍总击杀 = 队内所有成员击杀之和。有效队伍击杀 = max(0, 队伍总击杀 - 队伍让分)。两队有效击杀之差即为本场得分，赢的一方加分、输的一方扣分。

### 推荐算法

系统自动搜索最优让分组合，优化目标按优先级排列：
1. **最小方差** — 各玩家均分尽量接近
2. **最小分差** — 最高与最低均分之差尽量小
3. **最小让分总量** — 在同等公平性下，优先少让分

## 项目结构

```
├── pubg_web.py              # Web 应用入口
├── config.json              # 配置文件
├── requirements.txt         # Python 依赖
├── pubg_web_app/            # Web 应用模块
│   ├── server.py            # Flask 路由
│   ├── service.py           # 业务逻辑与校验
│   ├── templates/index.html # 前端页面
│   └── static/
│       ├── app.js           # 前端交互逻辑
│       └── styles.css       # 样式
└── pubg_cli_app/            # 核心模块
    ├── api.py               # PUBG API 客户端
    ├── cache.py             # 比赛数据缓存
    ├── config.py            # 配置加载
    ├── history.py           # 历史记录与画像
    └── scoring.py           # 让分算法
```
