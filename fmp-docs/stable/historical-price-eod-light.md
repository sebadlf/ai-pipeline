# Stock Chart Light

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/historical-price-eod-light](https://site.financialmodelingprep.com/developer/docs/stable/historical-price-eod-light)

Access simplified stock chart data using the FMP Basic Stock Chart API. This API provides essential charting information, including date, price, and trading volume, making it ideal for tracking stock performance with minimal data and creating basic price and volume charts.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/historical-price-eod/light?symbol=AAPL`

## Description
The FMP Basic Stock Chart API delivers streamlined access to stock charting data for users who need to track price movements without overwhelming complexity. This API offers:


Date & Price Information: Easily track daily price movements for a specific stock symbol.
Volume Data: Stay informed about trading activity with volume data included for each date.
Basic Charting Needs: Ideal for generating simple stock price and volume charts for historical performance analysis.

This API is perfect for users and developers who want a quick, straightforward way to visualize stock data without the need for detailed technical indicators.

Example Use Case
A financial app can use the Basic Stock Chart API to display a minimal chart showing a stock’s daily closing price and volume, allowing users to quickly assess its performance over time.

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
`historical-price-eod-full`, `intraday-1-min`, `intraday-1-hour`, `historical-price-eod-non-split-adjusted`, `historical-price-eod-dividend-adjusted`
