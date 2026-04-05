# 1-Minute Interval Index Price

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/index-intraday-1-min](https://site.financialmodelingprep.com/developer/docs/stable/index-intraday-1-min)

Retrieve 1-minute interval intraday data for stock indexes using the Intraday 1-Minute Price Data API. This API provides granular price information, helping users track short-term price movements and trading volume within each minute.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/historical-chart/1min?symbol=^GSPC`

## Description
The FMP Intraday 1-Minute Price Data API delivers high-frequency price data for stock indexes, offering insights into market fluctuations on a minute-by-minute basis. This level of detail is ideal for active traders and analysts who require real-time market insights for rapid decision-making. Key features include:


Granular Price Data: Access open, high, low, and close prices for each minute of the trading day.
Minute-by-Minute Tracking: Monitor short-term price movements and trends in real time.
Volume Information: Analyze trading volume for each minute, offering insights into market liquidity and activity levels.
Supports Intraday Trading: Perfect for day traders and high-frequency trading strategies that rely on detailed intraday data.

This API is particularly useful for day traders, quants, and financial analysts who need real-time data to track rapid price movements and make timely trading decisions.

Example Use Case
A day trader specializing in short-term stock index trades uses the Intraday 1-Minute Price Data API to track real-time price changes in the S&P 500 index (^GSPC). With access to minute-by-minute data, they can react to price movements and adjust their trading strategies in real time, optimizing their entry and exit points for maximum profitability.

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
        "^GSPC"
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
      ]
    ]
  }
}
```

## Related API slugs
`historical-sp-500`, `dow-jones`, `index-intraday-1-hour`, `index-historical-price-eod-light`, `sp-500`
