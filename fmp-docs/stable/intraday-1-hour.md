# 1 Hour Interval Stock Chart

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/intraday-1-hour](https://site.financialmodelingprep.com/developer/docs/stable/intraday-1-hour)

Track stock price movements over hourly intervals with the FMP 1-Hour Interval Stock Chart API. Access essential stock price and volume data, including open, high, low, and close prices for each hour, to analyze broader intraday trends with precision.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/historical-chart/1hour?symbol=AAPL`

## Description
The FMP 1-Hour Interval Stock Chart API is perfect for traders and investors who want to monitor hourly stock price movements. By delivering key price metrics every hour, this API provides a clear and comprehensive view of intraday stock trends. Key features include:


Hourly Price Data: Access open, high, low, and close prices updated every hour to stay on top of stock performance throughout the trading day.
Volume Tracking: Get insights into hourly trading volumes to understand market activity and liquidity at different times of the day.
Broader Timeframe Analysis: Ideal for traders who focus on medium-to-long intraday trends, the API helps visualize price movements over a broader timeframe.
Historical Data: Retrieve hourly historical data to analyze past price performance and identify trends over time.
Ideal for Trend and Pattern Recognition: Use this data to identify key patterns such as support, resistance, or trend reversals over hourly intervals.

Example Use Case
A swing trader uses the 1-Hour Interval Stock Chart API to track the hourly performance of Apple stock throughout the day, helping them make informed buy and sell decisions based on observed trends and trading volume changes.

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
`intraday-30-min`, `historical-price-eod-dividend-adjusted`, `intraday-1-min`, `historical-price-eod-non-split-adjusted`, `intraday-15-min`
