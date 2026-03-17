from __future__ import annotations

"""核心交易 Agent：继承 BaseAgent，实现 LLM 决策循环。"""

import asyncio
import json
from datetime import datetime, timezone
from decimal import Decimal

from litellm import acompletion
from loguru import logger

from src.agent.base_agent import BaseAgent
from src.agent.memory import AgentMemory
from src.agent.reflection import generate_reflection
from src.execution.signal import Action, TradeSignal
from src.integration.redis_bus import RedisBus
from src.market.data_feed import DataFeed, MarketSnapshot
from src.personality.ocean_model import OceanProfile
from src.personality.prompt_generator import generate_decision_prompt, generate_system_prompt
from src.personality.trait_to_constraint import TradingConstraints

SIGNAL_CHANNEL: str = "agent_signals"


def _clip(value: float, min_val: float, max_val: float) -> float:
    """将 value 限制在 [min_val, max_val] 范围内。"""
    return max(min_val, min(value, max_val))


def _snapshot_to_dict(snapshot: MarketSnapshot) -> dict:
    """MarketSnapshot -> prompt_generator 所需的 dict。"""
    return {
        "asset": snapshot.asset, "price": snapshot.price,
        "change_24h": snapshot.price_24h_change_pct, "volume": snapshot.volume_24h,
    }


class TradingAgent(BaseAgent):
    """基于 OCEAN 人格的交易 Agent，LLM 驱动决策。"""

    def __init__(
        self, agent_id: str, profile: OceanProfile,
        constraints: TradingConstraints, llm_config: dict,
        market_feed: DataFeed, redis_bus: RedisBus,
    ) -> None:
        """初始化交易 Agent。"""
        super().__init__(agent_id, profile.name)
        self._profile: OceanProfile = profile
        self._constraints: TradingConstraints = constraints
        self._llm_config: dict = llm_config
        self._market_feed: DataFeed = market_feed
        self._redis_bus: RedisBus = redis_bus
        self._memory: AgentMemory = AgentMemory(agent_id, redis_bus)
        self._system_prompt: str = generate_system_prompt(profile, constraints)
        self._positions: list[dict] = []
        self._portfolio_value: Decimal = Decimal("10000")
        self._trade_count: int = 0

    # ── 主循环 ──────────────────────────────────────────

    async def _run_loop(self) -> None:
        """按 rebalance 间隔循环执行决策。"""
        interval: int = self._constraints.rebalance_interval_seconds
        logger.info(f"[{self._name}] 决策间隔: {interval}秒")
        while self._running:
            try:
                await asyncio.sleep(interval)
                await self._decision_cycle()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.error(f"[{self._name}] 决策循环异常: {exc}")

    # ── 单次决策 ────────────────────────────────────────

    async def _decision_cycle(self) -> None:
        """一次完整决策：行情->Prompt->LLM->校验->发布。"""
        asset: str = self._constraints.allowed_assets[0]
        snapshot: MarketSnapshot | None = await self._market_feed.get_latest(asset)
        if snapshot is None:
            logger.warning(f"[{self._name}] 行情获取失败，跳过本轮")
            return
        context: str = await self._memory.get_context_for_decision()
        prompt: str = generate_decision_prompt(
            _snapshot_to_dict(snapshot), self._positions,
            context, float(self._portfolio_value),
        )
        raw: str | None = await self._call_llm(prompt)
        if raw is None:
            return
        signal: TradeSignal | None = self._validate_signal(raw, snapshot)
        if signal is not None:
            await self._execute_signal(signal)

    # ── LLM 调用（含重试） ─────────────────────────────

    async def _call_llm(self, user_prompt: str) -> str | None:
        """调用 LLM，失败自动重试，全部失败返回 None。"""
        retry_count: int = self._llm_config.get("retry_count", 3)
        retry_delay: float = self._llm_config.get("retry_delay_seconds", 5.0)
        messages: list[dict] = [
            {"role": "system", "content": self._system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        for attempt in range(1, retry_count + 1):
            try:
                resp = await acompletion(
                    model=self._llm_config["model"],
                    messages=messages,
                    temperature=self._llm_config.get("temperature", 0.3),
                    max_tokens=self._llm_config.get("max_tokens", 1024),
                    timeout=self._llm_config.get("timeout_seconds", 30),
                )
                return resp.choices[0].message.content  # type: ignore[union-attr]
            except Exception as exc:
                logger.warning(f"[{self._name}] LLM 失败 ({attempt}/{retry_count}): {exc}")
                if attempt < retry_count:
                    await asyncio.sleep(retry_delay)
        logger.error(f"[{self._name}] LLM 调用全部失败，跳过本轮")
        return None

    # ── JSON 解析 ───────────────────────────────────────

    def _parse_llm_response(self, raw: str) -> dict | None:
        """解析 LLM 原始输出为 dict，失败返回 None。"""
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.error(f"[{self._name}] JSON 解析失败，原始响应: {raw[:200]}")
            return None

    # ── 信号校验（硬约束由代码强制执行） ────────────────

    def _validate_signal(self, raw: str, snapshot: MarketSnapshot) -> TradeSignal | None:
        """校验 LLM 输出，clip 超限字段，返回合法 TradeSignal 或 None。"""
        data: dict | None = self._parse_llm_response(raw)
        if data is None:
            return None
        # action 校验
        action_str: str = str(data.get("action", "")).upper()
        if action_str not in ("BUY", "SELL", "HOLD"):
            logger.warning(f"[{self._name}] 无效 action: {action_str}")
            return None
        # asset 必须在允许列表中
        asset: str = str(data.get("asset", ""))
        if asset not in self._constraints.allowed_assets:
            logger.warning(f"[{self._name}] 资产 {asset} 不在允许列表中")
            return None
        # size_pct 和 confidence clip 到合法范围
        size_pct: float = _clip(float(data.get("size_pct", 0)), 0, self._constraints.max_position_pct)
        confidence: float = _clip(float(data.get("confidence", 0)), 0.0, 1.0)
        # 信心阈值检查
        if confidence < self._constraints.min_confidence_threshold:
            logger.info(f"[{self._name}] 信心不足 {confidence:.2f}，跳过")
            return None
        # 止损检查（尽责性高时强制要求）
        stop_loss: float | None = data.get("stop_loss_price")
        if self._constraints.require_stop_loss and stop_loss is None:
            logger.warning(f"[{self._name}] 缺少止损价格，约束要求必须设置")
            return None
        return TradeSignal(
            agent_id=self._agent_id, agent_name=self._name,
            timestamp=datetime.now(tz=timezone.utc),
            action=Action(action_str), asset=asset, size_pct=size_pct,
            entry_price=float(data.get("entry_price", snapshot.price)),
            stop_loss_price=stop_loss,
            take_profit_price=data.get("take_profit_price"),
            confidence=confidence,
            reasoning=str(data.get("reasoning", "")),
            personality_influence=str(data.get("personality_influence", "")),
            ocean_profile=self._profile.model_dump(exclude={"name"}),
        )

    # ── 信号执行（发布 + 记忆更新） ────────────────────

    async def _execute_signal(self, signal: TradeSignal) -> None:
        """发布信号到 Redis，更新记忆层。"""
        await self._redis_bus.publish(SIGNAL_CHANNEL, signal.model_dump())
        logger.info(
            f"[{self._name}] 信号: {signal.action.value} {signal.asset} "
            f"size={signal.size_pct:.1f}% conf={signal.confidence:.2f}"
        )
        # 更新 L1 + L2 记忆
        trade_data = signal.model_dump()
        self._memory.add_trade_result(trade_data)
        await self._memory.save_trade_to_l2(trade_data)
        # 更新 L1 tick（记录行情快照）
        self._memory.add_tick({"price": signal.entry_price, "asset": signal.asset})
        self._trade_count += 1
        # 每 10 笔交易触发反思（更新 L3 语义记忆）
        if self._trade_count % 10 == 0:
            await self._trigger_reflection()

    # ── 反思（每 10 笔交易触发） ──────────────────────

    async def _trigger_reflection(self) -> None:
        """调用反思模块，结果存入 L3 记忆。"""
        recent = await self._memory.get_recent_trades(count=10)
        result = await generate_reflection(
            self._name, self._profile, recent, self._llm_config,
        )
        if result and "summary" in result:
            await self._memory.add_reflection(result["summary"])
            logger.info(f"[{self._name}] 第 {self._trade_count} 笔，反思完成")
