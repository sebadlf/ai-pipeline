# Batch Market Cap

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/batch-market-cap](https://site.financialmodelingprep.com/developer/docs/stable/batch-market-cap)

Retrieve market capitalization data for multiple companies in a single request with the FMP Batch Market Capitalization API. This API allows users to compare the market size of various companies simultaneously, streamlining the analysis of company valuations.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/market-capitalization-batch?symbols=AAPL,MSFT,GOOG`

## Description
The FMP Batch Market Capitalization API offers a fast and efficient way to gather market cap data for several companies in one batch request. Key features include:


Multiple Companies in One Request: Retrieve the market capitalization for numerous companies in a single API call, saving time and effort.
Compare Market Sizes: Analyze and compare the market caps of different companies to evaluate their relative size and market standing.
Real-Time and Historical Market Caps: Access both current and past market capitalization data to track performance over time.

This API is perfect for investors, analysts, and portfolio managers who need to compare multiple companies at once, helping to identify investment opportunities and market trends quickly.

Example Use Case
An analyst researching tech giants can use the Batch Market Capitalization API to retrieve market cap data for Apple, Microsoft, and Google in one request. This allows them to quickly compare these companies' market sizes and assess their positions within the industry.

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
        "symbols*",
        "string",
        "AAPL,MSFT,GOOG"
      ]
    ]
  }
}
```

## Related API slugs
`market-cap`, `latest-mergers-acquisitions`, `historical-market-cap`, `employee-count`, `historical-employee-count`
