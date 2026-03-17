"""三层记忆系统（模仿 FinMem）。

L1 Working — tick + 交易结果，内存，同步 | L2 Episodic — 交易记录，Redis，50 笔
L3 Semantic — 反思总结，Redis，20 条
Redis key: agent:{id}:trades / agent:{id}:reflections
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from src.integration.redis_bus import RedisBus

_L1_TICK_LIMIT: int = 20
_L1_TRADE_LIMIT: int = 5
_L2_TRADE_LIMIT: int = 50
_L3_REFLECTION_LIMIT: int = 20


class AgentMemory:
    """Agent 三层记忆管理器。"""

    def __init__(self, agent_id: str, redis_bus: RedisBus) -> None:
        """初始化记忆系统。"""
        self._agent_id: str = agent_id
        self._redis: RedisBus = redis_bus
        self._working_ticks: list[dict] = []   # L1: 最多 20 条 tick
        self._working_trades: list[dict] = []  # L1: 最多 5 条交易

    # ── Redis key ─────────────────────────────────────

    @property
    def _l2_key(self) -> str:
        return f"agent:{self._agent_id}:trades"

    @property
    def _l3_key(self) -> str:
        return f"agent:{self._agent_id}:reflections"

    # ── L1 同步操作 ───────────────────────────────────

    def add_tick(self, tick: dict) -> None:
        """添加 tick 到 L1，超 20 条 FIFO 淘汰。"""
        self._working_ticks.append(tick)
        if len(self._working_ticks) > _L1_TICK_LIMIT:
            self._working_ticks = self._working_ticks[-_L1_TICK_LIMIT:]

    def add_trade_result(self, trade: dict) -> None:
        """添加交易结果到 L1（最近 5 条）。"""
        self._working_trades.append(trade)
        if len(self._working_trades) > _L1_TRADE_LIMIT:
            self._working_trades = self._working_trades[-_L1_TRADE_LIMIT:]

    # ── L2 异步操作（Redis） ─────────────────────────

    async def save_trade_to_l2(self, trade: dict) -> None:
        """保存完整交易记录到 Redis L2，超 50 笔自动淘汰。"""
        await self._redis.lpush_json(self._l2_key, trade)
        await self._redis.ltrim(self._l2_key, 0, _L2_TRADE_LIMIT - 1)
        logger.debug("[{}] L2 保存交易记录", self._agent_id)

    async def get_trade_count(self) -> int:
        """获取 L2 总交易数（判断是否触发反思）。"""
        try:
            r = await self._redis._ensure_connected()
            return await r.llen(self._l2_key)
        except Exception as exc:
            logger.error("[{}] 获取交易数失败: {}", self._agent_id, exc)
            return 0

    async def get_recent_trades(self, count: int = 10) -> list[dict]:
        """获取最近 N 笔交易（从 L2）。"""
        return await self._redis.lrange_json(self._l2_key, 0, count - 1)

    # ── L3 异步操作（Redis） ─────────────────────────

    async def add_reflection(self, summary: str) -> None:
        """添加反思总结到 L3，超 20 条自动淘汰。"""
        await self._redis.lpush_json(self._l3_key, summary)
        await self._redis.ltrim(self._l3_key, 0, _L3_REFLECTION_LIMIT - 1)
        logger.info("[{}] L3 新增反思总结", self._agent_id)

    async def _get_reflections(self, count: int = 5) -> list[str]:
        """获取最近 N 条反思（从 L3）。"""
        return await self._redis.lrange_json(self._l3_key, 0, count - 1)

    # ── C1: 相关性检索（替代纯 FIFO）──────────────────

    async def get_relevant_trades(
        self, current_asset: str, current_action: str, count: int = 5
    ) -> list[dict]:
        """检索与当前决策最相关的历史交易（而非最新的）。

        评分规则：同资产+3, 同action+2, 有盈亏记录+1, 时间衰减-0.1×天数(最多-2)
        """
        all_trades = await self.get_recent_trades(count=_L2_TRADE_LIMIT)
        if not all_trades:
            return []
        scored: list[tuple[float, dict]] = []
        for t in all_trades:
            score = 0.0
            if t.get("asset") == current_asset:
                score += 3.0
            if str(t.get("action", "")).upper() == current_action.upper():
                score += 2.0
            if "pnl" in t:
                score += 1.0
            scored.append((score, t))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [t for _, t in scored[:count]]

    # ── C2: 记忆衰减 ────────────────────────────────

    @staticmethod
    def _apply_decay(items: list[str], base_alpha: float = 0.95) -> list[tuple[str, float]]:
        """对列表项应用指数衰减权重。index=0 最新（权重=1.0）。"""
        return [(item, round(base_alpha ** i, 4)) for i, item in enumerate(items)]

    # ── 决策上下文 ────────────────────────────────────

    async def get_context_for_decision(
        self, current_asset: str = "", current_action: str = ""
    ) -> str:
        """从三层记忆提取上下文，拼成字符串插入 decision prompt。"""
        parts: list[str] = ["=== WORKING MEMORY ==="]
        # L1 价格
        if self._working_ticks:
            prices = [str(t.get("price", "N/A")) for t in self._working_ticks[-5:]]
            parts.append(f"Recent prices (last 5): {', '.join(prices)}")
        else:
            parts.append("Recent prices: No data yet.")
        # L1 交易
        if self._working_trades:
            for t in self._working_trades:
                parts.append(f"  Trade: {t.get('action')} {t.get('asset')} PnL={t.get('pnl', 'N/A')}")
        else:
            parts.append("Recent trades: None.")
        # L2 相关性检索（C1）
        parts.append("\n=== EPISODIC MEMORY ===")
        if current_asset:
            l2_trades = await self.get_relevant_trades(current_asset, current_action, count=5)
        else:
            l2_trades = await self.get_recent_trades(count=5)
        if l2_trades:
            for t in l2_trades:
                parts.append(f"  {t.get('action')} {t.get('asset')} "
                             f"entry={t.get('entry_price')} exit={t.get('exit_price')} "
                             f"PnL={t.get('pnl', 'N/A')}")
        else:
            parts.append("No historical trades.")
        # L3 反思（带衰减 C2）
        parts.append("\n=== SEMANTIC MEMORY ===")
        reflections = await self._get_reflections(count=5)
        if reflections:
            weighted = self._apply_decay(reflections, base_alpha=0.98)
            for ref, w in weighted:
                # 低权重项只展示前 50 字符
                display = ref if w >= 0.5 else (ref[:50] + "..." if len(ref) > 50 else ref)
                parts.append(f"  - [{w:.2f}] {display}")
        else:
            parts.append("No reflections yet.")
        return "\n".join(parts)
