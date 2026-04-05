# Historical Industry Performance

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/historical-industry-performance](https://site.financialmodelingprep.com/developer/docs/stable/historical-industry-performance)

Access historical performance data for industries using the Historical Industry Performance API. Track long-term trends and analyze how different industries have evolved over time across various stock exchanges.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/historical-industry-performance?industry=Biotechnology`

## Description
The FMP Historical Industry Performance API provides detailed historical data on the performance of various industries, such as Biotechnology, Technology, Financial Services, and more. This API allows users to track industry-specific performance metrics over time, providing insights into long-term trends and movements within the market. Key features include:


Industry-Level Historical Data: Access performance data for specific industries, including average percentage changes over time.
Exchange-Specific Performance: View how industries have performed on major stock exchanges like NASDAQ, NYSE, and others.
Long-Term Trend Analysis: Analyze historical data to identify long-term industry trends and market shifts.
Cross-Industry Comparisons: Compare the performance of different industries over time to identify growth areas and declining sectors.

This API is ideal for market analysts, portfolio managers, and investors who need to track industry-level performance trends to guide long-term investment strategies.

Example Use Case
A financial analyst uses the Historical Industry Performance API to track the historical performance of the Biotechnology industry on NASDAQ. By reviewing data from a specific date, showing an average gain of 1.15%, the analyst can assess how the industry has performed over time and determine if it aligns with their investment strategy.

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
        "industry*",
        "string",
        "Biotechnology"
      ],
      [
        "exchange",
        "string",
        "NASDAQ"
      ],
      [
        "from",
        "string",
        "2024-02-01"
      ],
      [
        "to",
        "string",
        "2024-03-01"
      ]
    ]
  }
}
```

## Related API slugs
`most-active`, `biggest-gainers`, `industry-PE-snapshot`, `sector-performance-snapshot`, `historical-sector-pe`
