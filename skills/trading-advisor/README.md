# Trading Advisor 技能使用说明

## 概述

Trading Advisor（持仓分析助手）是一个 QoderWork 技能，用于分析你的美股和期权持仓，提供技术面、消息面分析和交易操作建议。

## 触发方式

在 QoderWork 中输入以下任意关键词：

- `分析` / `analyze`
- `查询`
- `股票的操作建议`
- `持仓分析`
- `看看我的股票`
- `期权分析`
- `portfolio`

## 持仓文件

### 位置

将你的持仓数据保存为以下任一文件名（放在 QoderWork 工作区目录下）：

- `portfolio.json`
- `持仓.json`
- `我的持仓.json`

### 格式

参考 `portfolio-template.json` 模板，主要字段：

**股票持仓**：
```json
{
  "ticker": "AAPL",
  "type": "stock",
  "shares": 100,
  "avgCost": 185.50,
  "addedDate": "2024-01-15"
}
```

**期权持仓**：
```json
{
  "ticker": "TSLA",
  "type": "option",
  "optionType": "call",
  "strike": 200,
  "expiry": "2024-06-21",
  "contracts": 2,
  "avgCost": 15.30,
  "addedDate": "2024-03-10"
}
```

## 分析能力

### 技术面（股票）

- **MACD (12, 26, 9)** — 趋势方向与动能
- **KDJ (9, 3, 3)** — 超买超卖与买卖信号
- **布林带 (20, 2σ)** — 波动区间与压力支撑
- **成交量** — 量价配合度分析

### 消息面

- 分析师评级变化（最近 7 天）
- 财报与重大事件
- 行业动态
- 市场情绪与期权异动

### 交易规则

**期权类**：
- 到期前 7 天提醒平仓
- 单标的最多 4 张合约
- 盈利 100% 止盈

**股票类**：
- 盈利 5% 第一档止盈（卖 1/3）
- 盈利 10% 第二档止盈（再卖 1/3）
- 从最高点回撤 3% 触发移动止盈

## 数据来源

- 股票报价：Twelve Data / Alpha Vantage / Finnhub
- 历史K线：Twelve Data / Alpha Vantage
- 期权IV：本地代理 / 手动输入 / HV20 估算
- 新闻与评级：WebSearch 实时搜索

## 免责声明

所有分析仅供学习参考，不构成投资建议。
