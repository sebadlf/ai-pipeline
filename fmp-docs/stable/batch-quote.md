# Stock Batch Quote

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/batch-quote](https://site.financialmodelingprep.com/developer/docs/stable/batch-quote)

Retrieve multiple real-time stock quotes in a single request with the FMP Stock Batch Quote API. Access current prices, volume, and detailed data for multiple companies at once, making it easier to track large portfolios or monitor multiple stocks simultaneously.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/batch-quote?symbols=AAPL`

## Description
The FMP Stock Batch Quote API allows users to retrieve quotes for multiple stocks in one streamlined request. This API is ideal for:


Portfolio Monitoring: Track several stocks in real-time, perfect for investors or portfolio managers who need to monitor multiple holdings at once.
Data Efficiency: Instead of making multiple calls, get detailed stock data for several companies in a single API request, reducing complexity.
Comprehensive Stock Insights: Access detailed data for each stock, including the current price, volume, day high/low, 50-day and 200-day moving averages, and more.

This API ensures efficient data retrieval for investors, traders, and applications requiring comprehensive real-time stock data for multiple symbols.

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
        "symbols*",
        "string",
        "AAPL"
      ]
    ]
  }
}
```

## Related API slugs
`quote`, `quote-short`, `quote-change`, `full-mutualfund-quotes`, `full-commodities-quotes`
