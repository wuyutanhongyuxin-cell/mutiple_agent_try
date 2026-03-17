# execution — 执行层

## 用途
交易信号定义、纸上交易执行、多 Agent 信号聚合、全局风控。

## 文件清单
- `signal.py` — TradeSignal 数据结构（~42行）
- `account.py` — AgentAccount 虚拟账户（~178行）
- `paper_trader.py` — PaperTrader 纸上交易管理器（~109行）
- `stats_helper.py` — Sharpe / MaxDD / 胜率 / 盈亏比计算（~75行）
- `aggregator.py` — 信号聚合器 independent + voting 模式（~96行）
- `risk_manager.py` — 全局风控（~79行）

## 依赖关系
- 本目录依赖：pydantic, decimal
- 被以下模块依赖：agent/, integration/, main.py
