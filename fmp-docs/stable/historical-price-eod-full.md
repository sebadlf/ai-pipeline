# Stock Price and Volume Data

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/historical-price-eod-full](https://site.financialmodelingprep.com/developer/docs/stable/historical-price-eod-full)

Access full price and volume data for any stock symbol using the FMP Comprehensive Stock Price and Volume Data API. Get detailed insights, including open, high, low, close prices, trading volume, price changes, percentage changes, and volume-weighted average price (VWAP).

## Endpoint URLs
- `https://financialmodelingprep.com/stable/historical-price-eod/full?symbol=AAPL`

## Description
The FMP Comprehensive Stock Price and Volume Data API provides in-depth data on stock performance over time, making it an essential tool for analysts, traders, and investors. With this API, users can:


Detailed Price Data: Access complete price information, including opening, closing, high, and low prices for each trading day.
Trading Volume Insights: Retrieve data on daily trading volume to analyze liquidity and market activity.
Price Changes and Percentages: Track absolute price changes and percentage shifts to evaluate price movements.
VWAP (Volume-Weighted Average Price): Get the VWAP to measure the average price based on volume, helping to identify price trends and market behavior.

This API is perfect for users who require detailed and accurate stock price and volume data to make informed trading and investment decisions.

Example Use Case
A financial analyst can use the Comprehensive Stock Price and Volume Data API to monitor Apple's daily stock performance, analyzing price changes, VWAP, and trading volume to spot trends and predict future price movements.

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
        "2025-09-09"
      ],
      [
        "to",
        "date",
        "2025-12-09"
      ]
    ]
  }
}
```

## Related API slugs
`intraday-1-hour`, `intraday-1-min`, `historical-price-eod-non-split-adjusted`, `intraday-30-min`, `historical-price-eod-light`
