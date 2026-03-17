# todo.md — Personality Trading Agents 进度跟踪

## Phase 1：纸上交易验证 ✅

### Step 1-7：核心实现 ✅ (126 tests)
全部完成，详见 git 历史。

### Phase A：回测引擎重建 ✅
- [x] `execution/cost_model.py` — 滑点+手续费+资金费率模型
- [x] 成本模型集成到 `account.py` / `paper_trader.py`
- [x] `scripts/llm_backtest.py` — 真实 LLM 回测（多runs+pass^k）
- [x] `utils/anonymizer.py` — 资产匿名化防 look-ahead bias
- [x] `config/trading.yaml` 新增 costs + anonymize 配置

### Phase B：Agent 稳定性增强 ✅
- [x] `execution/consistency_monitor.py` — 行为漂移检测（三级KL阈值）
- [x] `agent/multi_sample.py` — 多采样投票机制（默认3次）
- [x] `agent/trading_agent.py` 集成多采样+匿名化+prompt hash
- [x] `personality/prompt_generator.py` — Prompt 版本控制(SHA256)
- [x] `execution/signal.py` 新增 prompt_hash + llm_model 字段

### Phase C：记忆系统升级 ✅
- [x] `agent/memory.py` — 相关性检索（替代纯FIFO）
- [x] `agent/memory.py` — 指数衰减机制（L3 alpha=0.98）

### Phase D：数据层增强 ✅
- [x] `market/data_feed.py` — 修复24h变化（用24条前价格）
- [x] `market/data_feed.py` — MarketSnapshot 新增 open_price + funding_rate
- [x] `config/trading.yaml` 成本配置段
- [x] `config/llm.yaml` 多采样+限流配置

### Phase E：全局风控增强 ✅
- [x] `execution/risk_manager.py` — 新增 Agent 级风控

### Phase F：可观测性增强 ✅
- [x] `utils/trade_logger.py` — 全链路交易日志
- [x] `integration/telegram_notifier.py` — 漂移告警+成本报告

### 测试 ✅
- [x] 148 tests 全部通过（原126 + 新增22）
- [x] test_cost_model.py (8 tests)
- [x] test_consistency_monitor.py (7 tests)
- [x] test_anonymizer.py (7 tests)

---

## Phase 2（未来）
- [ ] 接入真实DEX（GRVT/Paradex）
- [ ] Agent人格动态进化（反思自动调参）
- [ ] 情绪数据源接入（Twitter/Telegram sentiment）
- [ ] 投票模式实盘验证
