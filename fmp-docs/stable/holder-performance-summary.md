# Holder Performance Summary

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/holder-performance-summary](https://site.financialmodelingprep.com/developer/docs/stable/holder-performance-summary)

The Holder Performance Summary API provides insights into the performance of institutional investors based on their stock holdings. This data helps track how well institutional holders are performing, their portfolio changes, and how their performance compares to benchmarks like the S&P 500.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/institutional-ownership/holder-performance-summary?cik=0001067983&page=0`

## Description
The Holder Performance Summary API allows users to view performance metrics for institutional holders, such as market value changes, portfolio turnover, and relative performance against benchmarks. This API is ideal for:


Institutional Investor Analysis: Track how well institutional investors are performing based on stock picks, changes in holdings, and market value.
Portfolio Turnover Analysis: See how frequently an institution buys or sells securities, providing insights into their trading strategy.
Performance Benchmarking: Compare an institution's performance against the S&P 500 and other benchmarks over different timeframes (1 year, 3 years, 5 years).

This API offers a comprehensive view of an institutional holder’s performance over time, helping investors and analysts track key players in the market.

Example Use Case
An investment manager can use the Holder Performance Summary API to analyze Berkshire Hathaway's performance over the last five years and compare it to the S&P 500, assessing how well their investment strategy has fared.

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
        "cik*",
        "string",
        "0001067983"
      ],
      [
        "page",
        "number",
        "0"
      ]
    ]
  }
}
```

## Related API slugs
`filings-extract-with-analytics-by-holder`, `industry-summary`, `positions-summary`, `latest-filings`, `filings-extract`
