# Insider Trade Statistics

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/insider-trade-statistics](https://site.financialmodelingprep.com/developer/docs/stable/insider-trade-statistics)

Analyze insider trading activity with the Insider Trade Statistics API. This API provides key statistics on insider transactions, including total purchases, sales, and trends for specific companies or stock symbols.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/insider-trading/statistics?symbol=AAPL`

## Description
The FMP Insider Trade Statistics API provides comprehensive statistical data on insider trading activity for a specific stock symbol. This includes the total number of transactions, shares acquired or disposed of, and the overall ratio of acquisitions to dispositions. By analyzing these trends, users can gain insights into corporate sentiment and market behavior. Key features include:


Transaction Breakdown: Access statistics on insider acquisitions and dispositions for a specific company.
Acquired vs. Disposed Ratio: Analyze the ratio of shares acquired to shares disposed of, revealing insider sentiment.
Quarterly Data: View insider trading activity on a quarterly basis, helping you track changes in trading patterns over time.
Total and Average Transactions: Get detailed statistics on total purchases and sales, along with average transaction sizes.

This API is ideal for investors, analysts, and financial researchers who need to analyze patterns and trends in insider trading activity to make informed investment decisions.

Example Use Case
A financial analyst uses the Insider Trade Statistics API to examine insider trading trends for Apple (AAPL) in the third quarter of 2024. By reviewing the ratio of shares disposed of to those acquired, along with the total number of sales, the analyst can assess whether insiders are showing confidence in the company’s future.

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
`search-reporting-name`, `acquisition-ownership`, `latest-insider-trade`, `all-transaction-types`, `search-insider-trades`
