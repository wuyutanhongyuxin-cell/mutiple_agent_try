from __future__ import annotations

"""历史回测脚本：使用 MockDataFeed + 规则决策（不调LLM）生成 PnL 对比。

用法: python scripts/backtest.py [--csv data/btc_1h_2024.csv]
"""

import argparse
import asyncio
from datetime import datetime, timezone

from rich.console import Console
from rich.table import Table

from src.execution.paper_trader import PaperTrader
from src.execution.signal import Action, TradeSignal
from src.market.data_feed import MockDataFeed
from src.market.indicators import calculate_rsi
from src.personality.ocean_model import OceanProfile, PRESET_PROFILES
from src.personality.trait_to_constraint import TradingConstraints, ocean_to_constraints

GLOBAL_CONFIG: dict = {
    "major_assets": ["BTC-PERP", "ETH-PERP"],
    "all_assets": ["BTC-PERP", "ETH-PERP", "SOL-PERP", "ARB-PERP", "DOGE-PERP"],
}
ASSET: str = "BTC-PERP"


def _should_buy(
    profile: OceanProfile,
    constraints: TradingConstraints,
    price_change: float,
    rsi: float | None,
) -> bool:
    """根据简化规则判断是否买入。"""
    # 高尽责性(C>70)：仅在 RSI<30 时买入
    if profile.conscientiousness > 70:
        if rsi is None or rsi >= 30:
            return False
    # 高外向性(E>50)：追涨（价格上涨时买）
    if profile.extraversion > 50:
        return price_change > 0
    # 低外向性(E<=50)：逆向（价格下跌时买）
    return price_change < 0


def _make_signal(
    agent_id: str, profile: OceanProfile,
    constraints: TradingConstraints, action: Action, price: float,
) -> TradeSignal:
    """构造交易信号。止损=stop_loss_pct，止盈=2倍止损。"""
    is_buy = action == Action.BUY
    sl = price * (1 - constraints.stop_loss_pct / 100) if is_buy else None
    tp = price * (1 + constraints.stop_loss_pct * 2 / 100) if is_buy else None
    o, c, e, a, n = (profile.openness, profile.conscientiousness,
                      profile.extraversion, profile.agreeableness, profile.neuroticism)
    return TradeSignal(
        agent_id=agent_id, agent_name=profile.name,
        timestamp=datetime.now(tz=timezone.utc), action=action, asset=ASSET,
        size_pct=constraints.max_position_pct, entry_price=price,
        stop_loss_price=sl, take_profit_price=tp, confidence=c / 100.0,
        reasoning="backtest_rule",
        personality_influence=f"O={o} C={c} E={e} A={a} N={n}",
        ocean_profile={"O": o, "C": c, "E": e, "A": a, "N": n},
    )


async def run_backtest(csv_path: str) -> list[dict]:
    """执行回测主循环，返回各 Agent 绩效列表。"""
    feed = MockDataFeed(csv_path=csv_path, asset=ASSET)
    trader = PaperTrader()

    # 准备 Agent 列表
    agents: list[tuple[str, OceanProfile, TradingConstraints]] = []
    for name, profile in PRESET_PROFILES.items():
        aid = f"bt_{name}"
        cons = ocean_to_constraints(profile, GLOBAL_CONFIG)
        trader.register_agent(aid, 10000.0)
        agents.append((aid, profile, cons))

    price_history: list[float] = []
    prev_price: float = 0.0
    step: int = 0
    async for snapshot in feed.subscribe([ASSET]):
        price = snapshot.price
        price_history.append(price)
        change = (price - prev_price) / prev_price * 100 if prev_price > 0 else 0.0
        rsi = calculate_rsi(price_history, period=14)

        trader.update_prices({ASSET: price})  # 触发止损/止盈
        for aid, profile, cons in agents:
            if _should_buy(profile, cons, change, rsi):
                sig = _make_signal(aid, profile, cons, Action.BUY, price)
                if sig.confidence >= cons.min_confidence_threshold:
                    trader.execute_signal(sig)

        if step > 0 and step % 24 == 0:  # 24条≈1天
            trader.record_daily_returns()

        prev_price = price
        step += 1
        if step >= 2000:  # 最多跑 2000 条
            break

    return trader.get_leaderboard()


def print_results(results: list[dict]) -> None:
    """用 Rich 表格输出回测结果。"""
    console = Console()
    table = Table(title="回测结果 - Agent PnL 对比")
    table.add_column("#", style="dim", width=3)
    table.add_column("Agent", style="cyan")
    table.add_column("总资产", justify="right")
    table.add_column("已实现PnL", justify="right")
    table.add_column("Sharpe", justify="right")
    table.add_column("MaxDD", justify="right")
    table.add_column("胜率", justify="right")
    table.add_column("交易数", justify="right")

    for i, r in enumerate(results, 1):
        pnl = r["realized_pnl"]
        style = "green" if pnl >= 0 else "red"
        table.add_row(
            str(i), r["agent_id"],
            f"${r['portfolio_value']:,.2f}",
            f"[{style}]${pnl:+,.2f}[/{style}]",
            f"{r['sharpe_ratio']:.2f}",
            f"{r['max_drawdown_pct']:.1f}%",
            f"{r['win_rate']:.1%}",
            str(r["total_trades"]),
        )
    console.print(table)


def main() -> None:
    """解析参数并执行回测。"""
    parser = argparse.ArgumentParser(description="Agent 历史回测")
    parser.add_argument("--csv", default="data/btc_1h_2024.csv", help="行情CSV路径")
    args = parser.parse_args()

    Console().print(f"[bold]开始回测[/bold]  CSV={args.csv}")
    results = asyncio.run(run_backtest(args.csv))
    print_results(results)


if __name__ == "__main__":
    main()
