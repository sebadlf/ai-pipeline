# Industry PE Snapshot

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/industry-pe-snapshot](https://site.financialmodelingprep.com/developer/docs/stable/industry-pe-snapshot)

View price-to-earnings (P/E) ratios for different industries using the Industry P/E Snapshot API. Analyze valuation levels across various industries to understand how each is priced relative to its earnings.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/industry-pe-snapshot?date=2024-02-01`

## Description
The FMP Industry P/E Snapshot API provides detailed information on the price-to-earnings (P/E) ratios of various industries, such as Advertising Agencies, Technology, and Healthcare. This API enables users to compare industry-specific valuation levels across stock exchanges like NASDAQ and NYSE, offering insights into which industries are overvalued or undervalued. Key features include:


P/E Ratios by Industry: Access the most recent P/E ratios for industries across major stock exchanges.
Daily Updates: Get daily snapshots of industry P/E ratios, helping track changes in valuations over time.
Exchange-Specific Data: Analyze how industries are valued on different exchanges, such as NASDAQ or NYSE.
Cross-Industry Comparisons: Compare P/E ratios across industries to identify potential investment opportunities or risks.

This API is perfect for investors, analysts, and financial professionals looking to evaluate industry-specific valuations for making informed investment decisions.

Example Use Case
An investor uses the Industry P/E Snapshot API to assess a specific industry on NASDAQ. Knowing the P/E ratio, the investor can determine if the industry is overvalued and adjust their portfolio accordingly.

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
        "date*",
        "string",
        "2024-02-01"
      ],
      [
        "exchange",
        "string",
        "NASDAQ"
      ],
      [
        "industry",
        "string",
        "Biotechnology"
      ]
    ]
  }
}
```

## Related API slugs
`industry-PE-snapshot`, `sector-performance-snapshot`, `historical-sector-pe`, `most-active`, `historical-industry-pe`
