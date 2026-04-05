# Stock Quote

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/quote](https://site.financialmodelingprep.com/developer/docs/stable/quote)

Access real-time stock quotes with the FMP Stock Quote API. Get up-to-the-minute prices, changes, and volume data for individual stocks.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/quote?symbol=AAPL`

## Description
The FMP Stock Quote API provides detailed, real-time stock data for individual stocks, making it a valuable tool for investors, traders, and financial analysts. This API helps you:


Monitor Real-Time Prices: Stay updated with the latest stock prices to make informed trading decisions.
Analyze Stock Movements: Track key data points such as price changes, volume, day highs and lows, and yearly highs and lows.
Portfolio Tracking: Use real-time data to keep track of stock performance in your portfolio.

Whether you are monitoring individual stocks or building trading strategies, this API ensures that you have the most up-to-date information.

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
      ]
    ]
  }
}
```

## Related API slugs
`full-mutualfund-quotes`, `aftermarket-trade`, `quote-short`, `batch-quote-short`, `batch-quote`
