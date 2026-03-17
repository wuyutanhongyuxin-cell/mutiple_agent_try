# Personality-Conditioned Multi-Agent Crypto Trading System

> **English | [中文](README_CN.md)**

> A Multi-Agent Crypto Paper Trading System driven by Big Five (OCEAN) Personality Model

[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-126%20passed-brightgreen.svg)](#)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Overview

This system uses **Big Five personality theory (OCEAN model)** to create diverse crypto trading agents. Each agent has a unique personality profile that deterministically shapes its trading behavior — risk tolerance, position sizing, asset selection, and decision frequency.

Multiple agents run in parallel, each making independent decisions via LLM (through `litellm`), while hard constraints enforced by code prevent any agent from exceeding its personality-derived limits.

```
                    ┌─────────────────────────────────┐
                    │       OCEAN Personality          │
                    │  O=90 C=80 E=25 A=20 N=10       │
                    └──────────┬──────────────────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
      ┌──────────────┐ ┌────────────┐ ┌──────────────┐
      │ System Prompt│ │ Constraints│ │ Memory (3L)  │
      │ (personality)│ │ (hard code)│ │ W / E / S    │
      └──────┬───────┘ └─────┬──────┘ └──────┬───────┘
             │               │               │
             └───────┬───────┘               │
                     ▼                       │
              ┌──────────────┐               │
              │   LLM Call   │◄──────────────┘
              │  (litellm)   │
              └──────┬───────┘
                     ▼
              ┌──────────────┐
              │  Validate &  │  ← clip to constraints
              │  Clip Signal │
              └──────┬───────┘
                     ▼
              ┌──────────────┐
              │ Paper Trader │  → PnL, Sharpe, MaxDD
              └──────────────┘
```

---

## Key Design Principles

| Principle | Implementation |
|-----------|---------------|
| **LLM suggests, code enforces** | `_validate_signal()` clips all values to constraint ranges |
| **Personality = continuous, not categorical** | OCEAN scores 0-100, not MBTI types |
| **Deterministic constraints** | `trait_to_constraint.py` uses fixed formulas, no LLM influence |
| **Agent isolation** | Each agent has independent memory, positions, and PnL |
| **No float for money** | All financial calculations use `decimal.Decimal` |

---

## OCEAN Personality Mapping

Each of the five dimensions maps to specific trading behaviors:

| Dimension | High Score (→100) | Low Score (→0) |
|-----------|-------------------|----------------|
| **O**penness | Trades altcoins, novel strategies | BTC/ETH only, conservative |
| **C**onscientiousness | Strict stop-loss, disciplined | Impulsive, ignores risk mgmt |
| **E**xtraversion | Momentum-chasing, follows crowd | Contrarian, independent |
| **A**greeableness | Herding, aligns with consensus | Challenges consensus, shorts |
| **N**euroticism | Tight stops, frequent cutting | Holds through drawdowns |

### Constraint Formulas (Hard-Coded)

```python
max_position_pct     = clip(5 + (100 - N) * 0.25, 5, 30)
stop_loss_pct        = clip(1 + (100 - N) * 0.14, 1, 15)
max_drawdown_pct     = clip(2 + (100 - N) * 0.18, 2, 20)
max_concurrent_pos   = clip(1 + O // 20, 1, 6)
rebalance_interval   = 300s if N>70, 3600s if N>40, 86400s otherwise
allowed_assets       = all if O>60, major_only otherwise
use_sentiment        = E > 50
momentum_weight      = E / 100
contrarian_weight    = (100 - A) / 100
require_stop_loss    = C > 50
min_confidence       = clip(C * 0.008, 0.2, 0.8)
```

---

## 7 Preset Personality Archetypes

| Archetype | O | C | E | A | N | Trading Style |
|-----------|---|---|---|---|---|---------------|
| **Calm Innovator** | 90 | 80 | 25 | 20 | 10 | Explores new assets, disciplined, contrarian |
| **Conservative Anxious** | 15 | 85 | 20 | 70 | 90 | BTC/ETH only, very tight stops, checks every 5min |
| **Aggressive Risk-Taker** | 85 | 20 | 80 | 15 | 10 | All assets, momentum-chasing, loose risk mgmt |
| **Disciplined Momentum** | 50 | 90 | 75 | 50 | 30 | Follows trends with strict discipline |
| **Contrarian Value** | 60 | 75 | 10 | 10 | 25 | Fades the crowd, patient, value-focused |
| **Balanced Moderate** | 50 | 50 | 50 | 50 | 50 | Middle-of-the-road on everything |
| **Emotional Chaser** | 70 | 15 | 90 | 80 | 75 | FOMO-driven, herding, tight stops |

---

## Project Structure

```
personality-trading-agents/
├── config/
│   ├── agents.yaml          # Agent personality configs (OCEAN params)
│   ├── trading.yaml         # Trading params (assets, data feed, risk)
│   └── llm.yaml             # LLM provider config
├── src/
│   ├── personality/         # OCEAN model, constraint mapping, prompt generation
│   ├── agent/               # Base agent, trading agent, 3-layer memory, reflection
│   ├── market/              # Data feeds (Mock/Live), technical indicators
│   ├── execution/           # Signal model, paper trader, aggregator, risk manager
│   ├── integration/         # Redis pub/sub, Telegram notifications
│   ├── utils/               # Config loader, logger
│   └── main.py              # System entry point
├── tests/                   # 126 tests covering all modules
├── scripts/
│   ├── dashboard.py         # Rich terminal real-time dashboard
│   ├── backtest.py          # Historical backtesting
│   └── create_agents_config.py  # Bulk config generation
└── pyproject.toml
```

---

## Three-Layer Memory System (FinMem-inspired)

| Layer | Name | Content | Capacity | Storage | Trigger |
|-------|------|---------|----------|---------|---------|
| L1 | Working | Recent 20 ticks + last 5 trade results | 20+5 | In-memory | Every decision |
| L2 | Episodic | Full trade records (price, PnL, reasoning) | 50 trades | Redis | Every trade |
| L3 | Semantic | Reflection summaries (natural language) | 20 entries | Redis | Every 10 trades |

---

## Quick Start

### 1. Install Dependencies

```bash
pip install -e ".[dev]"
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your API keys:
# ANTHROPIC_API_KEY, REDIS_URL, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
```

### 3. Run Tests

```bash
pytest tests/ -v
# 126 tests should pass
```

### 4. Start the System

```bash
python -m src.main
```

### 5. Run Dashboard (separate terminal)

```bash
python scripts/dashboard.py
```

### 6. Run Backtest

```bash
python scripts/backtest.py
```

---

## Signal Aggregation Modes

| Mode | Description | Use Case |
|------|-------------|----------|
| `independent` | Each agent's signal executes independently | A/B testing personalities |
| `voting` | Weighted vote: `confidence x historical_sharpe` | Ensemble decisions |

Configure in `config/trading.yaml`:
```yaml
aggregator:
  mode: "independent"  # or "voting"
  signal_window_seconds: 120
```

---

## Tech Stack

| Component | Choice | Reason |
|-----------|--------|--------|
| Language | Python 3.9+ | Async ecosystem |
| LLM Interface | `litellm` | Provider-agnostic (Claude/GPT/local) |
| Data Validation | Pydantic v2 | Type safety + serialization |
| Message Bus | Redis pub/sub | Signal broadcasting |
| Notifications | aiogram 3.x | Telegram alerts |
| Logging | loguru | Structured, colored output |
| Dashboard | rich | Terminal UI |
| Testing | pytest + pytest-asyncio | 126 tests, full coverage |

**Intentionally excluded**: pandas, numpy, django, flask, sqlalchemy (keeping it lightweight).

---

## Telegram Notifications

The system pushes:
- Trade signals with full reasoning
- Stop-loss / take-profit triggers
- Agent reflection reports (every 10 trades)
- Daily leaderboard reports

Example signal notification:
```
🧠 Calm Innovator (O90/C80/E25/A20/N10)
📊 BUY BTC-PERP @ $67,200
💰 Size: 25% | SL: $64,000 | TP: $72,000
🎯 Confidence: 0.85
💭 On-chain data shows whale accumulation, RSI oversold
🔑 Dominant: O-dimension — willing to build position during pullback
```

---

## Development Roadmap

### Phase 1 (Current): Paper Trading Validation
- [x] OCEAN personality model + 7 archetypes
- [x] Deterministic constraint mapping
- [x] LLM-driven decision loop with hard constraint enforcement
- [x] 3-layer memory system
- [x] Paper trading with full PnL tracking
- [x] Signal aggregation (independent + voting)
- [x] Global risk management
- [x] Telegram notifications
- [x] Rich terminal dashboard
- [x] Historical backtesting

### Phase 2 (Future): Live Trading
- [ ] Connect to real DEX (GRVT/Paradex)
- [ ] Dynamic personality evolution (auto-tuning from reflections)
- [ ] Sentiment data sources (Twitter/Telegram)
- [ ] Voting mode live validation

---

## License

MIT
