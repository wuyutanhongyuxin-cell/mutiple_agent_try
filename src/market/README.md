# market — 行情数据

## 用途
行情数据源抽象层和技术指标计算。

## 文件清单
- `data_feed.py` — DataFeed 抽象 + MockDataFeed + LiveDataFeed（~179行）
- `indicators.py` — RSI / SMA / MACD 技术指标（~78行）

## 依赖关系
- 本目录依赖：aiohttp, pydantic
- 被以下模块依赖：agent/
