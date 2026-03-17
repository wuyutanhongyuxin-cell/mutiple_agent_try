from __future__ import annotations

"""
Personality-Conditioned Multi-Agent Crypto Trading System 主入口。

加载配置 → 初始化组件 → 创建 Agent → 并行运行 → 优雅关闭。

用法：python -m src.main
"""

import asyncio
import signal
import sys
from decimal import Decimal
from typing import Any

from loguru import logger

from src.agent.trading_agent import TradingAgent
from src.execution.aggregator import SignalAggregator
from src.execution.paper_trader import PaperTrader
from src.execution.risk_manager import RiskManager
from src.integration.redis_bus import RedisBus
from src.integration.telegram_notifier import TelegramNotifier
from src.market.data_feed import DataFeed, LiveDataFeed, MockDataFeed
from src.personality.ocean_model import PRESET_PROFILES, OceanProfile
from src.personality.trait_to_constraint import ocean_to_constraints
from src.utils.config_loader import load_agents_config, load_llm_config, load_trading_config


def _build_asset_config(trading_cfg: dict[str, Any]) -> dict[str, list[str]]:
    """从 trading.yaml 提取资产配置。"""
    assets = trading_cfg["trading"]["assets"]
    return {"major_assets": assets["major"], "all_assets": assets["all"]}


def _build_market_feed(trading_cfg: dict[str, Any]) -> DataFeed:
    """根据配置创建行情数据源。"""
    feed_cfg = trading_cfg["trading"]["data_feed"]
    if feed_cfg["type"] == "mock":
        return MockDataFeed(csv_path=feed_cfg.get("mock_csv_path", ""))
    # 实时数据源
    return LiveDataFeed(interval_seconds=feed_cfg.get("interval_seconds", 60))


def _resolve_profile(agent_cfg: dict[str, Any]) -> OceanProfile:
    """从 agent 配置解析 OceanProfile（支持预定义原型或自定义参数）。"""
    if "preset" in agent_cfg:
        return PRESET_PROFILES[agent_cfg["preset"]]
    return OceanProfile(**agent_cfg["custom"])


def _create_agents(
    agents_cfg: dict[str, Any],
    llm_cfg: dict[str, Any],
    asset_config: dict[str, list[str]],
    market_feed: DataFeed,
    redis_bus: RedisBus,
    paper_trader: PaperTrader,
    telegram: TelegramNotifier,
) -> list[TradingAgent]:
    """遍历 agents.yaml 创建所有 TradingAgent。"""
    agents: list[TradingAgent] = []
    for cfg in agents_cfg["agents"]:
        profile = _resolve_profile(cfg)
        constraints = ocean_to_constraints(profile, asset_config)
        capital = cfg.get("initial_capital", 10000)
        paper_trader.register_agent(cfg["id"], capital)

        agent = TradingAgent(
            agent_id=cfg["id"],
            profile=profile,
            constraints=constraints,
            llm_config=llm_cfg.get("llm", {}),
            market_feed=market_feed,
            redis_bus=redis_bus,
        )
        # 注入 paper_trader 和 telegram（TradingAgent 构造函数不含这两个参数）
        agent._paper_trader = paper_trader  # noqa: SLF001
        agent._telegram = telegram  # noqa: SLF001
        agents.append(agent)
        logger.info(f"创建 Agent: {profile.name} ({cfg['id']})")
    return agents


def _register_shutdown(shutdown_event: asyncio.Event) -> None:
    """注册 SIGINT / SIGTERM 优雅关闭处理器。"""
    def _handle(sig: int, _frame: Any) -> None:
        logger.info(f"收到信号 {sig}，开始优雅关闭...")
        shutdown_event.set()

    signal.signal(signal.SIGINT, _handle)
    # Windows 不支持 SIGTERM，安全跳过
    if sys.platform != "win32":
        signal.signal(signal.SIGTERM, _handle)


async def main() -> None:
    """主函数：初始化并启动所有组件。"""
    # 1. 加载配置
    agents_cfg = load_agents_config()
    trading_cfg = load_trading_config()
    llm_cfg = load_llm_config()

    # 2. 初始化基础设施
    redis_bus = RedisBus()
    await redis_bus.connect()
    telegram = TelegramNotifier()
    await telegram.initialize()

    # 3. 初始化执行层
    paper_trader = PaperTrader()
    risk_cfg = trading_cfg["trading"]["risk"]
    risk_manager = RiskManager(
        global_max_drawdown_pct=risk_cfg["global_max_drawdown_pct"],
        global_max_daily_loss_pct=risk_cfg["global_max_daily_loss_pct"],
    )

    # 4. 创建数据源和 Agent
    market_feed = _build_market_feed(trading_cfg)
    asset_config = _build_asset_config(trading_cfg)
    agents = _create_agents(
        agents_cfg, llm_cfg, asset_config, market_feed, redis_bus, paper_trader, telegram,
    )

    # 5. 初始化风控（基准 = 所有 Agent 初始资金之和）
    total_capital = sum(a.get("initial_capital", 10000) for a in agents_cfg["agents"])
    risk_manager.initialize(Decimal(str(total_capital)))

    # 6. 初始化聚合器
    agg_cfg = trading_cfg["trading"]["aggregator"]
    _aggregator = SignalAggregator(
        mode=agg_cfg["mode"],
        signal_window_seconds=agg_cfg.get("signal_window_seconds", 120),
        paper_trader=paper_trader,
        redis_bus=redis_bus,
    )

    # 7. 注册优雅关闭
    shutdown_event = asyncio.Event()
    _register_shutdown(shutdown_event)

    # 8. 启动所有 Agent（每个 Agent 是独立的 asyncio Task）
    for agent in agents:
        await agent.start()
    logger.info(f"系统启动完成，共 {len(agents)} 个 Agent 运行中")

    # 9. 等待关闭信号
    await shutdown_event.wait()

    # 10. 优雅关闭
    logger.info("正在关闭所有 Agent...")
    for agent in agents:
        await agent.stop()
    await redis_bus.disconnect()
    await telegram.close()
    logger.info("系统已完全关闭")


if __name__ == "__main__":
    asyncio.run(main())
