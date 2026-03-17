from __future__ import annotations

"""真实 LLM 回测：调用 LLM 决策循环，支持多次运行收集一致性数据。

用法: python scripts/llm_backtest.py --csv data/btc_1h_2024.csv --runs 3 --agents 3
特性: 真实 LLM 调用 | --runs N 一致性 | --anonymize 防 bias | 限流控制
"""

import argparse
import asyncio
import sys
from pathlib import Path

# 确保项目根目录在 path 中
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from litellm import acompletion
from loguru import logger
from rich.console import Console

from src.execution.cost_model import CostConfig
from src.execution.paper_trader import PaperTrader
from src.market.data_feed import MockDataFeed
from src.personality.ocean_model import PRESET_PROFILES, OceanProfile
from src.personality.prompt_generator import (
    generate_decision_prompt, generate_system_prompt, get_prompt_hash)
from src.personality.trait_to_constraint import ocean_to_constraints
from src.utils.anonymizer import AssetAnonymizer
from src.utils.config_loader import load_llm_config, load_trading_config

from _backtest_helpers import (  # 同目录辅助模块
    calc_consistency, parse_llm_json, print_results, validate_signal)

console = Console()


def _parse_args() -> argparse.Namespace:
    """解析命令行参数。"""
    p = argparse.ArgumentParser(description="真实 LLM 回测脚本")
    p.add_argument("--csv", required=True, help="历史数据 CSV 路径")
    p.add_argument("--runs", type=int, default=3, help="重复运行次数（收集一致性）")
    p.add_argument("--agents", type=int, default=3, help="使用前 N 个预定义原型")
    p.add_argument("--anonymize", action="store_true", help="启用资产匿名化")
    p.add_argument("--max-steps", type=int, default=500, help="最大回测步数")
    return p.parse_args()


def _select_profiles(n: int) -> list[OceanProfile]:
    """选取前 N 个预定义人格原型。"""
    return [PRESET_PROFILES[k] for k in list(PRESET_PROFILES.keys())[:n]]


def _build_global_config(trading_cfg: dict) -> dict:
    """从 trading.yaml 构建 ocean_to_constraints 所需的全局配置。"""
    assets = trading_cfg.get("trading", {}).get("assets", {})
    return {
        "major_assets": assets.get("major", ["BTC-PERP", "ETH-PERP"]),
        "all_assets": assets.get("all", ["BTC-PERP", "ETH-PERP"]),
    }


async def _run_agent_step(
    agent: dict, snapshot: object, trader: PaperTrader,
    anonymizer: AssetAnonymizer | None, model: str,
    temperature: float, max_tokens: int,
) -> None:
    """单个 Agent 的单步决策：构造 prompt → 调用 LLM → 校验 → 执行。"""
    market_data = {
        "asset": snapshot.asset, "price": snapshot.price,
        "change_24h": snapshot.price_24h_change_pct,
        "volume": snapshot.volume_24h,
    }
    if anonymizer:
        market_data = anonymizer.anonymize_market_data(market_data)
    # 获取持仓信息
    account = trader._accounts[agent["id"]]
    positions_info = [
        {"asset": p.asset, "size": p.size_pct,
         "entry_price": float(p.entry_price), "unrealized_pnl": 0.0}
        for p in account.positions
    ]
    pv = float(account.get_portfolio_value({"BTC-PERP": snapshot.price}))
    dec_prompt = generate_decision_prompt(market_data, positions_info, "", pv)
    # 调用 LLM
    try:
        resp = await acompletion(
            model=model, temperature=temperature, max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": agent["sys_prompt"]},
                {"role": "user", "content": dec_prompt},
            ],
        )
        raw = resp.choices[0].message.content or ""
    except Exception as e:
        logger.error(f"[{agent['id']}] LLM 调用失败: {e}")
        agent["actions"].append("ERROR")
        return
    parsed = parse_llm_json(raw)
    if parsed is None:
        agent["actions"].append("PARSE_FAIL")
        return
    signal = validate_signal(
        parsed, agent["id"], agent["profile"], agent["constraints"],
        snapshot.price, anonymizer, agent["prompt_hash"], model)
    if signal is None:
        agent["actions"].append("HOLD")
    else:
        trader.execute_signal(signal)
        agent["actions"].append(signal.action.value)


async def _run_single_backtest(
    profiles: list[OceanProfile], feed_path: str, max_steps: int,
    anonymize: bool, trading_cfg: dict, llm_cfg: dict,
) -> dict[str, dict]:
    """执行单次回测，返回 {agent_id: {name, pnl, sharpe, trades, actions}}。"""
    global_cfg = _build_global_config(trading_cfg)
    llm = llm_cfg.get("llm", {})
    model = llm.get("model", "claude-sonnet-4-20250514")
    temperature = llm.get("temperature", 0.3)
    max_tokens = llm.get("max_tokens", 1024)
    rpm = llm.get("max_calls_per_minute", 20)
    sleep_between = 60.0 / rpm if rpm > 0 else 3.0
    cost_raw = trading_cfg.get("trading", {}).get("costs", {})
    trader = PaperTrader(cost_config=CostConfig(**cost_raw) if cost_raw else CostConfig())
    all_assets = global_cfg["all_assets"]
    anonymizer = AssetAnonymizer(all_assets) if anonymize else None
    # 初始化各 Agent
    agents: list[dict] = []
    for i, profile in enumerate(profiles):
        aid = f"agent_{i}"
        constraints = ocean_to_constraints(profile, global_cfg)
        sys_prompt = generate_system_prompt(profile, constraints)
        if anonymizer:
            sys_prompt = anonymizer.anonymize(sys_prompt)
        trader.register_agent(aid, 10000.0)
        agents.append({
            "id": aid, "profile": profile, "constraints": constraints,
            "sys_prompt": sys_prompt, "prompt_hash": get_prompt_hash(sys_prompt),
            "actions": [],
        })
    # 步进回测主循环
    feed = MockDataFeed(csv_path=feed_path, asset="BTC-PERP")
    for step in range(max_steps):
        snapshot = await feed.get_latest("BTC-PERP")
        if snapshot is None:
            break
        trader.update_prices({"BTC-PERP": snapshot.price})
        if step > 0 and step % 24 == 0:  # 每 24 条 K 线记录日收益率
            trader.record_daily_returns()
        for agent in agents:
            interval_steps = max(1, agent["constraints"].rebalance_interval_seconds // 3600)
            if step % interval_steps != 0:
                agent["actions"].append("SKIP")
                continue
            await _run_agent_step(
                agent, snapshot, trader, anonymizer, model, temperature, max_tokens)
            await asyncio.sleep(sleep_between)  # 限流
        if (step + 1) % 50 == 0:
            console.print(f"  [dim]步骤 {step + 1}/{max_steps}[/dim]")
    # 收集结果
    results: dict[str, dict] = {}
    for agent in agents:
        stats = trader.get_agent_stats(agent["id"])
        results[agent["id"]] = {
            "name": agent["profile"].name,
            "pnl": stats["realized_pnl"] + stats["unrealized_pnl"],
            "sharpe": stats["sharpe_ratio"],
            "trades": stats["total_trades"],
            "actions": agent["actions"],
        }
    return results


async def main() -> None:
    """入口：解析参数、执行多轮回测、输出报告。"""
    args = _parse_args()
    trading_cfg = load_trading_config()
    llm_cfg = load_llm_config()
    profiles = _select_profiles(args.agents)
    console.print(f"[bold]LLM 回测启动[/bold]: {args.runs} 轮 x {len(profiles)} 个 Agent")
    console.print(f"  CSV: {args.csv} | 最大步数: {args.max_steps} | 匿名化: {args.anonymize}")
    all_runs: list[dict[str, dict]] = []
    for run_idx in range(args.runs):
        console.print(f"\n[bold yellow]-- Run {run_idx + 1}/{args.runs} --[/bold yellow]")
        result = await _run_single_backtest(
            profiles, args.csv, args.max_steps, args.anonymize, trading_cfg, llm_cfg)
        all_runs.append(result)
    consistency = calc_consistency(all_runs) if len(all_runs) > 1 else {}
    console.print()
    print_results(all_runs, consistency)


if __name__ == "__main__":
    asyncio.run(main())
