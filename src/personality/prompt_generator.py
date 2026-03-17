"""Prompt 生成器：将 OCEAN 人格参数和交易约束转化为 LLM Prompt。

Prompt 全部用英文（LLM 英文推理更准），日志和通知用中文。
"""

from src.personality.ocean_model import OceanProfile
from src.personality.trait_to_constraint import TradingConstraints

# ── 维度描述映射：(全名, 高分含义, 低分含义) ──
_TRAIT_DESC: dict[str, tuple[str, str, str]] = {
    "openness": (
        "Openness",
        "explores new altcoins, novel strategies, and high-volatility assets",
        "sticks to BTC/ETH only, conservative and proven strategies",
    ),
    "conscientiousness": (
        "Conscientiousness",
        "strict stop-loss discipline, rigorous position sizing, rule-following",
        "impulsive trading, may ignore risk management rules",
    ),
    "extraversion": (
        "Extraversion",
        "follows market sentiment, momentum-chasing, trend-following",
        "contrarian, independent judgment, fades the crowd",
    ),
    "agreeableness": (
        "Agreeableness",
        "herding behavior, aligns with market consensus",
        "challenges consensus, comfortable taking the opposite side",
    ),
    "neuroticism": (
        "Neuroticism",
        "extreme loss aversion, very tight stops, frequent cutting of losers",
        "emotionally stable, can hold through drawdowns patiently",
    ),
}


def _build_personality_section(profile: OceanProfile) -> str:
    """段落2：逐维度列出分数及交易行为含义。"""
    lines: list[str] = ["## Your Personality Profile (Big Five / OCEAN)"]
    for attr, (name, high, low) in _TRAIT_DESC.items():
        score: int = getattr(profile, attr)
        desc = high if score > 50 else low
        lines.append(f"- {name} ({attr[0].upper()}={score}): {desc}")
    return "\n".join(lines)


def _build_constraints_section(c: TradingConstraints) -> str:
    """段落3：注入硬约束，LLM 不得超出。"""
    lines: list[str] = ["## HARD CONSTRAINTS (you MUST NOT exceed these):"]
    for name, info in c.model_fields.items():
        lines.append(f"- {info.description or name}: {getattr(c, name)}")
    return "\n".join(lines)


def generate_system_prompt(profile: OceanProfile, constraints: TradingConstraints) -> str:
    """生成 System Prompt（英文），Agent 初始化时调用一次。"""
    role = (
        "You are a cryptocurrency trader with a distinct personality. "
        f"Your trading persona is '{profile.name}'. "
        "Your personality directly shapes how you analyze markets and make decisions."
    )
    personality = _build_personality_section(profile)
    hard = _build_constraints_section(constraints)
    output_fmt = (
        "## Output Format\n"
        "You must respond with a single JSON object containing these fields:\n"
        '- "action": "BUY" | "SELL" | "HOLD"\n'
        '- "asset": string (e.g. "BTC-PERP")\n'
        '- "size_pct": float (percentage of portfolio)\n'
        '- "entry_price": float\n'
        '- "stop_loss_price": float\n'
        '- "take_profit_price": float\n'
        '- "confidence": float between 0 and 1\n'
        '- "reasoning": string (your analysis)\n'
        '- "personality_influence": string (which trait dominated this decision)'
    )
    rules = (
        "## Rules\n"
        "- Do NOT fabricate market data or prices.\n"
        "- Do NOT exceed any hard constraint listed above.\n"
        "- Do NOT output anything other than the JSON object.\n"
        "- Do NOT wrap the JSON in markdown code fences.\n"
        "You MUST respond with ONLY a valid JSON object."
    )
    return "\n\n".join([role, personality, hard, output_fmt, rules])


def generate_decision_prompt(
    market_data: dict,
    positions: list,
    memory_context: str,
    portfolio_value: float,
) -> str:
    """生成 Decision Prompt（英文），每次决策循环调用。"""
    # 行情
    asset = market_data.get("asset", "UNKNOWN")
    price = market_data.get("price", 0)
    change = market_data.get("change_24h", 0)
    volume = market_data.get("volume", 0)
    market_sec = (
        f"## Current Market Data\n"
        f"- Asset: {asset}\n"
        f"- Price: ${price:,.2f}\n"
        f"- 24h Change: {change:+.2f}%\n"
        f"- 24h Volume: ${volume:,.0f}"
    )
    # 持仓
    if positions:
        pl = ["## Current Positions"]
        for p in positions:
            pl.append(
                f"- {p.get('asset', '?')}: size={p.get('size', 0)}, "
                f"entry=${p.get('entry_price', 0):,.2f}, "
                f"unrealized_pnl=${p.get('unrealized_pnl', 0):,.2f}"
            )
        pos_sec = "\n".join(pl)
    else:
        pos_sec = "## Current Positions\nNo open positions."
    # 资产
    used = sum(p.get("size", 0) * p.get("entry_price", 0) for p in positions)
    port_sec = (
        f"## Portfolio\n"
        f"- Total Value: ${portfolio_value:,.2f}\n"
        f"- Available Balance: ${portfolio_value - used:,.2f}"
    )
    # 记忆
    mem_sec = f"## Memory & Context\n{memory_context}" if memory_context else ""
    # 组装
    instruction = (
        "Based on the above data and your personality, decide your next action. "
        "Respond with ONLY a valid JSON object."
    )
    parts = [market_sec, pos_sec, port_sec]
    if mem_sec:
        parts.append(mem_sec)
    parts.append(instruction)
    return "\n\n".join(parts)
