# Stock Price Change

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/quote-change](https://site.financialmodelingprep.com/developer/docs/stable/quote-change)

Track stock price fluctuations in real-time with the FMP Stock Price Change API. Monitor percentage and value changes over various time periods, including daily, weekly, monthly, and long-term.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/stock-price-change?symbol=AAPL`

## Description
The FMP Stock Price Change API allows you to stay updated on the real-time performance of stocks by tracking price changes across multiple timeframes. This API is essential for:


Real-Time Monitoring: Track percentage and value changes in stock prices over different time intervals, such as 1 day, 5 days, 1 month, and up to 10 years.
Investment Strategy: Use the data to identify trends in stock performance, helping you make informed decisions based on short-term and long-term price movements.
Comparative Analysis: Compare price changes across multiple timeframes to assess a stock’s performance over time, helping you adjust your portfolio or strategy accordingly.

This API is a valuable resource for investors, traders, and analysts who need detailed stock performance data to inform their strategies and decisions.

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
`full-exchange-quotes`, `quote`, `aftermarket-trade`, `batch-aftermarket-quote`, `aftermarket-quote`
