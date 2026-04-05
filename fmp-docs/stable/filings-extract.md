# Filings Extract

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/filings-extract](https://site.financialmodelingprep.com/developer/docs/stable/filings-extract)

The SEC Filings Extract API allows users to extract detailed data directly from official SEC filings. This API provides access to key information such as company shares, security details, and filing links, making it easier to analyze corporate disclosures.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/institutional-ownership/extract?cik=0001388838&year=2023&quarter=3`

## Description
The SEC Filings Extract API offers a streamlined way to retrieve detailed information from SEC filings. This is ideal for investors, analysts, and financial professionals who need to analyze official company reports and gain insights into ownership structures, security details, and other critical data.
This API is perfect for:


SEC Filings Analysis: Extract key information from SEC filings, such as shares owned, value, and security details.
Ownership Tracking: Monitor changes in company ownership over time by accessing filed reports.
Filing Comparison: Compare detailed data from different filing periods to track trends and changes.

This API provides a structured and simplified way to access complex SEC filings data, helping you save time and focus on the analysis.

Example Use Case
An investment firm uses the SEC Filings Extract API to track changes in ownership for a specific company by extracting data from quarterly 13F filings. This helps the firm identify trends and adjust its investment strategy accordingly.

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
        "0001388838"
      ],
      [
        "year*",
        "string",
        "2023"
      ],
      [
        "quarter*",
        "string",
        "3"
      ]
    ]
  }
}
```

## Related API slugs
`positions-summary`, `holder-performance-summary`, `latest-filings`, `industry-summary`, `form-13f-filings-dates`
