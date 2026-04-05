# Historical Industry PE

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/historical-industry-pe](https://site.financialmodelingprep.com/developer/docs/stable/historical-industry-pe)

Access historical price-to-earnings (P/E) ratios by industry using the Historical Industry P/E API. Track valuation trends across various industries to understand how market sentiment and valuations have evolved over time.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/historical-industry-pe?industry=Biotechnology`

## Description
The FMP Historical Industry P/E API provides detailed historical data on the price-to-earnings (P/E) ratios of different industries, such as Biotechnology, Financial Services, and Consumer Goods. This API helps users track how industry valuations have changed over time, offering insights into long-term trends and market shifts. Key features include:


Industry-Specific P/E Data: Access historical P/E ratios for specific industries, helping you track how valuations have evolved over time.
Exchange-Specific Analysis: View industry P/E ratios across different exchanges, including NASDAQ, NYSE, and more.
Long-Term Valuation Trends: Analyze historical data to identify valuation trends and shifts in market sentiment within industries.
Cross-Industry Comparisons: Compare P/E ratios across multiple industries to understand which sectors are undervalued or overvalued.

This API is ideal for investors, market analysts, and portfolio managers who need to assess industry-specific valuation trends to inform long-term investment strategies.

Example Use Case
A financial analyst uses the Historical Industry P/E API to review the historical P/E ratios of the Biotechnology industry on NASDAQ. By tracking how the P/E ratio has evolved over time, the analyst can determine whether the industry’s current valuation reflects long-term market trends and decide if it's a good investment opportunity.

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
`biggest-losers`, `industry-performance-snapshot`, `historical-industry-performance`, `industry-PE-snapshot`, `most-active`
