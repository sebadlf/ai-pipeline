# Stock Grades Summary

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/grades-summary](https://site.financialmodelingprep.com/developer/docs/stable/grades-summary)

Quickly access an overall view of analyst ratings with the FMP Grades Summary API. This API provides a consolidated summary of market sentiment for individual stock symbols, including the total number of strong buy, buy, hold, sell, and strong sell ratings. Understand the overall consensus on a stock’s outlook with just a few data points.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/grades-consensus?symbol=AAPL`

## Description
The FMP Grades Summary API simplifies the process of gauging market sentiment by delivering a clear breakdown of analyst ratings. It is particularly valuable for:


Market Sentiment Assessment: Quickly assess the overall market opinion on a stock, whether it's leaning towards buy, hold, or sell.
Investment Decision Support: Use the consensus ratings to guide your investment decisions, knowing how many analysts recommend buying or selling a stock.
Portfolio Monitoring: Keep an eye on stocks in your portfolio by reviewing changes in analyst sentiment and adjusting your positions accordingly.
Streamlined Stock Analysis: For users looking to get a high-level understanding of a stock's market position, the summarized data offers an efficient way to digest complex rating information.

This API helps investors and analysts make informed decisions with a quick glance at how the market views a stock.

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
`historical-grades`, `grades`, `price-target-consensus`, `ratings-snapshot`, `price-target-summary`
