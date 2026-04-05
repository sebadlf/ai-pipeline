# Historical Sector PE

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/historical-sector-pe](https://site.financialmodelingprep.com/developer/docs/stable/historical-sector-pe)

Access historical price-to-earnings (P/E) ratios for various sectors using the Historical Sector P/E API. Analyze how sector valuations have evolved over time to understand long-term trends and market shifts.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/historical-sector-pe?sector=Energy`

## Description
The FMP Historical Sector P/E API provides detailed historical data on the price-to-earnings (P/E) ratios of different sectors, such as Energy, Technology, and Healthcare. This API helps users track how sector valuations have changed over time, offering insights into long-term trends and shifts in market sentiment. Key features include:


Historical P/E Ratios by Sector: Access historical P/E ratios for various sectors, allowing you to track valuation trends.
Exchange-Specific Data: Analyze sector valuations on specific exchanges, such as NASDAQ or NYSE.
Long-Term Analysis: Review historical data to identify sector trends and how valuations have evolved over time.
Cross-Sector Comparisons: Compare P/E ratios across multiple sectors to better understand relative valuations and market shifts.

This API is ideal for market analysts, portfolio managers, and investors who need to analyze sector-level valuation trends for long-term investment strategies.

Example Use Case
A portfolio manager uses the Historical Sector P/E API to review the historical P/E ratios of the Energy sector on NASDAQ. By examining the changes in P/E ratios over time, the manager can assess how the sector's valuation has evolved and make informed decisions about future investments.

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
        "string",
        "2024-02-01"
      ],
      [
        "exchange",
        "string",
        "NASDAQ"
      ],
      [
        "sector*",
        "string",
        "Energy"
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
`most-active`, `historical-industry-performance`, `historical-industry-pe`, `industry-performance-snapshot`, `biggest-gainers`
