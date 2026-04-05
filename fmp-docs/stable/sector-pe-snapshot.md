# Sector PE Snapshot

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/sector-pe-snapshot](https://site.financialmodelingprep.com/developer/docs/stable/sector-pe-snapshot)

Retrieve the price-to-earnings (P/E) ratios for various sectors using the Sector P/E Snapshot API. Compare valuation levels across sectors to better understand market valuations.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/sector-pe-snapshot?date=2024-02-01`

## Description
The FMP Sector P/E Snapshot API provides detailed data on the price-to-earnings (P/E) ratios of different market sectors, such as Basic Materials, Technology, Healthcare, and more. This API allows users to analyze sector-specific valuations, providing insights into how sectors are valued relative to their earnings. Key features include:


P/E Ratio by Sector: Access up-to-date P/E ratios for various sectors, helping you compare their relative valuations.
Exchange-Specific Data: View sector P/E ratios for specific exchanges, such as NASDAQ or NYSE.
Daily Updates: Receive daily updates on sector P/E ratios to track changes in valuation levels over time.
Valuation Comparisons: Compare the P/E ratios across multiple sectors to identify potential overvalued or undervalued sectors.

This API is ideal for investors, analysts, and portfolio managers who need to assess sector valuations for investment decision-making and market analysis.

Example Use Case
A portfolio manager uses the Sector P/E Snapshot API to compare the P/E ratios of different sectors on NASDAQ. By seeing that the Basic Materials sector has a P/E ratio of 15.69, they can assess whether this sector is overvalued or undervalued relative to other sectors and adjust their portfolio accordingly.

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
        "sector",
        "string",
        "Energy"
      ]
    ]
  }
}
```

## Related API slugs
`historical-sector-pe`, `sector-PE-snapshot`, `most-active`, `historical-industry-pe`, `biggest-losers`
