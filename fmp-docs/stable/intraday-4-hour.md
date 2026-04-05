# 4 Hour Interval Stock Chart

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/intraday-4-hour](https://site.financialmodelingprep.com/developer/docs/stable/intraday-4-hour)

Analyze stock price movements over extended intraday periods with the FMP 4-Hour Interval Stock Chart API. Access key stock price and volume data in 4-hour intervals, perfect for tracking longer intraday trends and understanding broader market movements.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/historical-chart/4hour?symbol=AAPL`

## Description
The FMP 4-Hour Interval Stock Chart API provides traders and investors with essential data points over longer intraday time frames, allowing for comprehensive trend analysis. Ideal for users who want to track price movements in blocks larger than 1 hour but still within the trading day. Key features include:


4-Hour Price Intervals: Access open, high, low, and close prices, updated every 4 hours to provide a clearer view of intraday market trends.
Volume Data: Understand market activity by tracking trading volumes during each 4-hour period.
Ideal for Medium-Term Intraday Analysis: Longer intervals allow for deeper analysis of stock movements, helping to identify patterns and trends within a trading day.
Historical Data: Retrieve past 4-hour price data to study trends and create broader price movement models.
Intraday Market Strategy Support: Use the data to develop trading strategies that benefit from wider price movements and shifts within a trading session.

Example Use Case
A position trader uses the 4-Hour Interval Stock Chart API to monitor the longer intraday performance of Apple stock, allowing them to detect more substantial trends and price shifts without getting lost in short-term fluctuations.

## Parameters (from docs JSON)
```json
{
  "query": {
    "header": [
      "Query Parameter",
      "Type",
      "Example"
    ],
    "rows": [
      [
        "symbol*",
        "string",
        "AAPL"
      ],
      [
        "from",
        "date",
        "2024-01-01"
      ],
      [
        "to",
        "date",
        "2024-03-01"
      ],
      [
        "nonadjusted",
        "boolean",
        "false"
      ]
    ]
  }
}
```

## Related API slugs
`intraday-30-min`, `intraday-1-min`, `historical-price-eod-dividend-adjusted`, `intraday-15-min`, `historical-price-eod-full`
