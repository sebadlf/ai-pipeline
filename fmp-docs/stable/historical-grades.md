# Historical Stock Grades

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/historical-grades](https://site.financialmodelingprep.com/developer/docs/stable/historical-grades)

Access a comprehensive record of analyst grades with the FMP Historical Grades API. This tool allows you to track historical changes in analyst ratings for specific stock symbol

## Endpoint URLs
- `https://financialmodelingprep.com/stable/grades-historical?symbol=AAPL`

## Description
The FMP Historical Grades API offers an in-depth look at how analysts have rated specific stocks in the past. This API is perfect for:


Trend Analysis: Investors can use historical ratings to spot long-term trends in market sentiment for a stock, helping to predict future price movements.
Investment Strategy Optimization: By tracking changes in analyst sentiment over time, investors can adjust their strategies based on whether analysts are becoming more bullish or bearish.
Benchmarking Performance: Compare a stock’s historical ratings to its actual performance, enabling a deeper understanding of how well the stock has lived up to expectations.
Market Sentiment Tracking: Use the API to analyze how buy, hold, and sell ratings have changed, providing insight into broader market confidence or caution around a stock.

This API empowers investors with historical context, offering a valuable tool for long-term financial analysis and decision-making.

Example Use Case
A portfolio manager can utilize the Historical Grades API to observe changes in analyst sentiment for a particular stock, helping them adjust their strategy based on evolving market outlooks.

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
        "limit",
        "number",
        "100"
      ]
    ]
  }
}
```

## Related API slugs
`price-target-summary`, `grades-summary`, `financial-estimates`, `grades`, `ratings-snapshot`
