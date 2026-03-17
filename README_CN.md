# 基于人格的多 Agent 加密货币交易系统

> **[English](README.md) | 中文**

> 用心理学 Big Five (OCEAN) 人格模型驱动的多 Agent 加密货币纸上交易系统——每个 Agent 拥有独特性格，性格决定交易风格

[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-126%20passed-brightgreen.svg)](#)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 项目简介

本系统使用 **Big Five 人格理论（OCEAN 模型）** 创建多样化的加密货币交易 Agent。每个 Agent 拥有独特的人格参数组合，这些参数**确定性地**塑造其交易行为——风险承受能力、仓位大小、资产选择和决策频率。

多个 Agent 并行运行，各自通过 LLM（`litellm` 统一接口）独立决策，同时由代码强制执行的硬约束确保任何 Agent 都不会超出其性格所决定的限制。

**核心理念**：LLM 只负责「建议」，代码负责「执行」。性格参数 → 硬编码公式 → 不可逾越的交易约束。

```
                    ┌─────────────────────────────────┐
                    │       OCEAN 人格参数              │
                    │  O=90 C=80 E=25 A=20 N=10       │
                    └──────────┬──────────────────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
      ┌──────────────┐ ┌────────────┐ ┌──────────────┐
      │ System Prompt│ │  硬约束     │ │ 三层记忆      │
      │ （性格注入）  │ │ （代码强制）│ │ W / E / S    │
      └──────┬───────┘ └─────┬──────┘ └──────┬───────┘
             │               │               │
             └───────┬───────┘               │
                     ▼                       │
              ┌──────────────┐               │
              │  LLM 调用    │◄──────────────┘
              │  (litellm)   │
              └──────┬───────┘
                     ▼
              ┌──────────────┐
              │  校验 & Clip │  ← 超限字段被裁剪到合法范围
              │  信号约束     │
              └──────┬───────┘
                     ▼
              ┌──────────────┐
              │  纸上交易     │  → PnL, Sharpe, 最大回撤
              └──────────────┘
```

---

## 核心设计原则

| 原则 | 实现方式 |
|------|---------|
| **LLM 建议，代码执行** | `_validate_signal()` 将所有值裁剪到约束范围内 |
| **人格 = 连续维度，非类型标签** | OCEAN 分数 0-100 连续值，不是 MBTI 类型 |
| **确定性约束** | `trait_to_constraint.py` 使用固定公式，不受 LLM 影响 |
| **Agent 完全隔离** | 每个 Agent 独立记忆、独立持仓、独立 PnL |
| **金额精确计算** | 所有金额使用 `decimal.Decimal`，禁止 float 算钱 |

---

## OCEAN 人格模型与交易映射

五个维度如何影响交易行为：

| 维度 | 缩写 | 高分 (→100) | 低分 (→0) |
|------|------|-------------|-----------|
| **开放性** | O | 探索山寨币、新策略、高波动资产 | 只做 BTC/ETH，保守策略 |
| **尽责性** | C | 严格止损、纪律执行、规则至上 | 冲动交易，忽视风控 |
| **外向性** | E | 追涨杀跌、跟随市场情绪 | 逆向交易、独立判断 |
| **宜人性** | A | 从众跟风、与市场共识一致 | 对抗市场共识、倾向做空 |
| **神经质** | N | 极度厌恶损失、止损极紧、频繁割肉 | 情绪稳定、能 hold 住回撤 |

### 约束映射公式（硬编码，LLM 不可覆盖）

```python
# 神经质(N)越高 → 仓位越小、止损越紧、检查越频繁
max_position_pct     = clip(5 + (100 - N) * 0.25, 5, 30)
stop_loss_pct        = clip(1 + (100 - N) * 0.14, 1, 15)
max_drawdown_pct     = clip(2 + (100 - N) * 0.18, 2, 20)
rebalance_interval   = N>70 → 5分钟, N>40 → 1小时, 否则 → 1天

# 开放性(O)越高 → 交易更多币种、同时持仓更多
max_concurrent_pos   = clip(1 + O // 20, 1, 6)
allowed_assets       = O>60 → 全部币种, 否则 → 仅主流(BTC/ETH)

# 外向性(E) → 情绪数据 + 动量权重
use_sentiment        = E > 50
momentum_weight      = E / 100

# 宜人性(A)越低 → 越倾向逆向交易
contrarian_weight    = (100 - A) / 100

# 尽责性(C)越高 → 越严格的止损和信心要求
require_stop_loss    = C > 50
min_confidence       = clip(C * 0.008, 0.2, 0.8)
```

---

## 7 个预定义人格原型

| 原型 | O | C | E | A | N | 交易风格 |
|------|---|---|---|---|---|---------|
| **冷静创新型** | 90 | 80 | 25 | 20 | 10 | 探索新资产、纪律严明、逆向思维 |
| **保守焦虑型** | 15 | 85 | 20 | 70 | 90 | 只做 BTC/ETH、极紧止损、每 5 分钟检查 |
| **激进冒险型** | 85 | 20 | 80 | 15 | 10 | 全币种、追涨杀跌、风控宽松 |
| **纪律动量型** | 50 | 90 | 75 | 50 | 30 | 跟随趋势但严格纪律 |
| **逆向价值型** | 60 | 75 | 10 | 10 | 25 | 逆势而行、耐心等待、价值导向 |
| **平衡中庸型** | 50 | 50 | 50 | 50 | 50 | 各维度均衡，中规中矩 |
| **情绪追涨型** | 70 | 15 | 90 | 80 | 75 | FOMO 驱动、从众跟风、紧止损 |

---

## 项目结构

```
personality-trading-agents/
├── config/
│   ├── agents.yaml          # Agent 人格配置（OCEAN 参数）
│   ├── trading.yaml         # 交易参数（交易对、数据源、风控）
│   └── llm.yaml             # LLM 配置（provider、model、温度）
├── src/
│   ├── personality/         # 人格引擎：OCEAN 模型 + 约束映射 + Prompt 生成
│   ├── agent/               # Agent 核心：基类 + 交易 Agent + 三层记忆 + 反思
│   ├── market/              # 行情数据：Mock/Live 数据源 + 技术指标
│   ├── execution/           # 执行层：信号结构 + 纸上交易 + 聚合器 + 风控
│   ├── integration/         # 外部集成：Redis 消息总线 + Telegram 通知
│   ├── utils/               # 工具：配置加载 + 日志
│   └── main.py              # 主入口
├── tests/                   # 126 个测试，覆盖全部核心模块
├── scripts/
│   ├── dashboard.py         # Rich 终端实时仪表盘
│   ├── backtest.py          # 历史回测
│   └── create_agents_config.py  # 批量生成 Agent 配置
└── pyproject.toml
```

---

## 三层记忆系统（FinMem 启发）

| 层级 | 名称 | 内容 | 容量 | 存储 | 触发时机 |
|------|------|------|------|------|---------|
| L1 | 工作记忆 | 最近 20 条 tick + 最近 5 次交易结果 | 20+5 | 内存 | 每次决策 |
| L2 | 情节记忆 | 完整交易记录（价格、盈亏、reasoning） | 50 笔 | Redis | 每次交易 |
| L3 | 语义记忆 | 反思总结（自然语言） | 20 条 | Redis | 每 10 笔交易 |

**记忆隔离**：每个 Agent 的记忆完全独立，互不共享，确保性格差异不被稀释。

---

## 快速开始

### 1. 安装依赖

```bash
pip install -e ".[dev]"
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 填入你的 API 密钥：
# ANTHROPIC_API_KEY=sk-ant-...
# REDIS_URL=redis://localhost:6379/0
# TELEGRAM_BOT_TOKEN=...
# TELEGRAM_CHAT_ID=...
```

### 3. 运行测试

```bash
pytest tests/ -v
# 应该看到 126 passed
```

### 4. 启动系统

```bash
python -m src.main
```

### 5. 启动仪表盘（另开一个终端）

```bash
python scripts/dashboard.py
```

### 6. 运行回测

```bash
python scripts/backtest.py
```

---

## 信号聚合模式

| 模式 | 说明 | 使用场景 |
|------|------|---------|
| `independent` | 每个 Agent 信号独立执行，各自计算 PnL | 对比实验：哪种性格表现最好 |
| `voting` | 按 `信心度 x 历史Sharpe` 加权投票 | 集成决策：综合多个性格的智慧 |

在 `config/trading.yaml` 中配置：
```yaml
aggregator:
  mode: "independent"  # 或 "voting"
  signal_window_seconds: 120
```

---

## 技术栈

| 组件 | 选型 | 说明 |
|------|------|------|
| 语言 | Python 3.9+ | asyncio 异步生态 |
| LLM 接口 | `litellm` | 统一接口，支持 Claude/GPT/本地模型 |
| 数据校验 | Pydantic v2 | 类型安全 + 序列化 |
| 消息队列 | Redis pub/sub | Agent 信号广播 |
| 通知推送 | aiogram 3.x | Telegram 实时告警 |
| 日志 | loguru | 结构化彩色输出 |
| 仪表盘 | rich | 终端实时 UI |
| 测试 | pytest + pytest-asyncio | 126 个测试，全模块覆盖 |

**刻意不用的依赖**：pandas、numpy、django、flask、sqlalchemy——保持轻量。

---

## Telegram 通知

系统推送以下事件：
- 交易信号（含完整决策理由）
- 止损/止盈触发
- Agent 反思报告（每 10 笔交易）
- 每日排行榜汇总

通知示例：
```
🧠 冷静创新型 (O90/C80/E25/A20/N10)
📊 BUY BTC-PERP @ $67,200
💰 Size: 25% | SL: $64,000 | TP: $72,000
🎯 Confidence: 0.85
💭 链上数据显示鲸鱼积累，RSI 超卖
🔑 主导维度: O—愿意在回调中建仓新头寸

📈 Daily Report - 2026-03-17
| # | Agent      | PnL    | Sharpe | MaxDD  | Trades |
|---|-----------|--------|--------|--------|--------|
| 1 | 冷静创新型 | +$320  | 1.85   | -3.2%  | 5      |
| 2 | 逆向价值型 | +$180  | 1.42   | -2.1%  | 3      |
| 3 | 激进冒险型 | -$450  | -0.32  | -12.5% | 12     |
```

---

## Agent 决策流程详解

每个 Agent 是独立的 `asyncio.Task`，主循环如下：

```
循环:
  1. 等待 rebalance_interval 秒（由 N 维度决定）
  2. 获取最新行情 → MarketSnapshot
  3. 从三层记忆提取决策上下文
  4. 生成 Decision Prompt（行情 + 持仓 + 记忆 + 总资产）
  5. 调用 LLM → 获取 JSON 格式的决策建议
  6. 校验 & Clip（关键步骤）：
     - action 必须是 BUY/SELL/HOLD
     - asset 必须在允许列表中（否则拒绝）
     - size_pct 裁剪到 [0, max_position_pct]
     - confidence 裁剪到 [0, 1]
     - 如果 require_stop_loss=True 但未设止损 → 拒绝
  7. 如果 confidence >= min_confidence_threshold：
     - 发布信号到 Redis
     - 更新 L1 + L2 记忆
  8. 每 10 笔交易 → 触发反思 → 更新 L3 记忆
```

---

## 开发路线图

### Phase 1（当前）：纸上交易验证
- [x] OCEAN 人格模型 + 7 个原型
- [x] 确定性约束映射
- [x] LLM 驱动决策 + 硬约束强制执行
- [x] 三层记忆系统
- [x] 纸上交易 + 完整绩效跟踪
- [x] 信号聚合（独立 + 投票模式）
- [x] 全局风控
- [x] Telegram 通知
- [x] Rich 终端仪表盘
- [x] 历史回测

### Phase 2（未来）：实盘交易
- [ ] 接入真实 DEX（GRVT/Paradex）
- [ ] 人格动态进化（反思驱动自动调参）
- [ ] 情绪数据源（Twitter/Telegram sentiment）
- [ ] 投票模式实盘验证

---

## 许可证

MIT
