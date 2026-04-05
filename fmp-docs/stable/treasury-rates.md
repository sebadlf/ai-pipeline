# Treasury Rates

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/treasury-rates](https://site.financialmodelingprep.com/developer/docs/stable/treasury-rates)

Access latest and historical Treasury rates for all maturities with the FMP Treasury Rates API. Track key benchmarks for interest rates across the economy.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/treasury-rates`

## Description
The Treasury Rates API provides real-time and historical data on Treasury rates for all maturities. These rates represent the interest rates that the US government pays on its debt obligations and serve as a critical benchmark for interest rates across the economy. Investors can use this API to:


Track Treasury Rates Over Time: Monitor the movement of Treasury rates and understand how they change over different periods.
Identify Interest Rate Trends: Analyze trends in interest rates to gain insights into the broader economic landscape.
Make Informed Investment Decisions: Use the data to inform investment strategies based on current and historical interest rate information.

This API is an invaluable tool for investors, analysts, and economists who need accurate and timely information on Treasury rates.

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
`economics-indicators`, `economics-calendar`, `market-risk-premium`
