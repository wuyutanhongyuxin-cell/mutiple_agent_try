# todo.md — Personality Trading Agents 进度跟踪

## Phase 1：纸上交易验证

### Step 1：基础设施 ⬜
- [ ] `pyproject.toml`
- [ ] `utils/config_loader.py`
- [ ] `utils/logger.py`
- [ ] `config/agents.yaml`
- [ ] `config/trading.yaml`
- [ ] `config/llm.yaml`
- [ ] `.env.example`

### Step 2：人格引擎 ⬜
- [ ] `personality/ocean_model.py` — 7个预定义原型
- [ ] `personality/trait_to_constraint.py` — 映射公式
- [ ] `personality/prompt_generator.py` — System + Decision Prompt
- [ ] `tests/test_personality/` — 全部通过 ✅?

### Step 3：数据层 ⬜
- [ ] `market/data_feed.py` — Mock + Live
- [ ] `market/indicators.py` — RSI/SMA/MACD
- [ ] `execution/signal.py` — TradeSignal
- [ ] `integration/redis_bus.py`

### Step 4：Agent核心 ⬜
- [ ] `agent/memory.py` — 三层记忆
- [ ] `agent/base_agent.py`
- [ ] `agent/trading_agent.py` — 决策循环
- [ ] `tests/test_agent/` — 全部通过 ✅?

### Step 5：执行层 ⬜
- [ ] `execution/paper_trader.py`
- [ ] `execution/aggregator.py`
- [ ] `execution/risk_manager.py`
- [ ] `tests/test_execution/` — 全部通过 ✅?

### Step 6：集成层 ⬜
- [ ] `integration/telegram_notifier.py`
- [ ] `agent/reflection.py`
- [ ] `src/main.py` — 主入口

### Step 7：工具 ⬜
- [ ] `scripts/dashboard.py`
- [ ] `scripts/create_agents_config.py`
- [ ] `scripts/backtest.py`

### 验收 ⬜
- [ ] pytest全通过
- [ ] 3 Agent并行运行
- [ ] 不同OCEAN → 不同行为（有数据证明）
- [ ] Telegram推送正常
- [ ] 仪表盘正常

---

## Phase 2（未来）
- [ ] 接入真实DEX（GRVT/Paradex）
- [ ] Agent人格动态进化（反思自动调参）
- [ ] 情绪数据源接入（Twitter/Telegram sentiment）
- [ ] 投票模式实盘验证
