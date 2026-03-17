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

## P0：对抗性测试 + 多市况回测 ✅

### P0-1：对抗性场景注入 ✅
- [x] `market/adversarial.py` — 5种对抗性场景（闪崩/暴涨/假突破/横盘/V反转）
- [x] `market/data_feed.py` — MockDataFeed 支持 adversarial_scenarios 参数注入
- [x] `tests/test_market/test_adversarial.py` — 9 个测试全部通过

### P0-2：多时间窗口回测 ✅
- [x] `scripts/generate_synthetic_data.py` — 从单CSV生成熊市/横盘/牛市合成数据
- [x] `scripts/llm_backtest.py` — 新增 --multi-market 参数，跨市况对比
- [x] `scripts/_backtest_helpers.py` — 新增 print_cross_market_results()
- [x] `scripts/llm_backtest.py` — 成本上限执行逻辑（max_cost_per_backtest_usd）

### Bug Fixes ✅
- [x] `scripts/_backtest_helpers.py` — model_version → llm_model 字段名修复
- [x] `config/trading.yaml` — funding_rate_8h 注释修正

---

## P1：高级记忆 + 元反思 ✅

### P1-1：多层反思机制 ✅
- [x] `agent/reflection.py` — 新增 generate_meta_reflection() 元反思
- [x] `agent/trading_agent.py` — 每30笔交易触发元反思，[META]标记存入L3
- [x] `tests/test_agent/test_trading_agent.py` — 4 个元反思测试

### P1-2：TF-IDF 记忆检索 ✅
- [x] `utils/tfidf.py` — 纯 Python TF-IDF + cosine similarity
- [x] `agent/memory.py` — get_relevant_trades() 改为 TF-IDF 混合检索
- [x] `tests/test_utils/test_tfidf.py` — 10 个 TF-IDF 测试
- [x] `tests/test_agent/test_memory.py` — 3 个 TF-IDF 记忆检索测试

### 测试 ✅
- [x] 174 tests 全部通过（原148 + 新增26）

---

## P2：知识图谱 + 微调数据导出 ✅

### P2-1：轻量知识图谱 ✅
- [x] `config/market_knowledge.json` — BTC/ETH 因果关系图谱（宏观/链上/衍生品）
- [x] `utils/knowledge_graph.py` — 图谱加载与查询（纯 JSON + 标准库）
- [x] `personality/prompt_generator.py` — Decision Prompt 注入 Market Knowledge 段
- [x] `tests/test_utils/test_knowledge_graph.py` — 6 个测试全部通过

### P2-2：决策轨迹导出 ✅
- [x] `scripts/export_training_data.py` — JSONL 微调数据导出（OpenAI/Qwen 格式）

---

## P3：辩论机制 + 执行策略抽象 ✅

### P3-1：Bull/Bear 辩论机制 ✅
- [x] `execution/debate.py` — 裁判 LLM 辩论模块（TradingAgents 启发）
- [x] `execution/aggregator.py` — voting 模式新增 enable_debate 参数
- [x] `config/trading.yaml` — 新增 enable_debate: false
- [x] `tests/test_execution/test_debate.py` — 7 个测试全部通过

### P3-2：执行策略抽象层 ✅
- [x] `execution/strategy.py` — ExecutionStrategy 接口 + RuleBasedStrategy
- [x] `agent/trading_agent.py` — _build_signal_from_data 委托给 Strategy（纯重构）
- [x] `tests/test_execution/test_strategy.py` — 6 个测试全部通过

### 测试 ✅
- [x] 193 tests 全部通过（原174 + 新增19）

---

## Phase 2（未来）
- [ ] 接入真实DEX（GRVT/Paradex）
- [ ] Agent人格动态进化（反思自动调参）
- [ ] 情绪数据源接入（Twitter/Telegram sentiment）
- [ ] 投票模式实盘验证
- [ ] RL 策略替换 RuleBasedStrategy
