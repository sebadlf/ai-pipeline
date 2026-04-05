# CIK

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/search-cik](https://site.financialmodelingprep.com/developer/docs/stable/search-cik)

Easily retrieve the Central Index Key (CIK) for publicly traded companies with the FMP CIK API. Access unique identifiers needed for SEC filings and regulatory documents for a streamlined compliance and financial analysis process.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/search-cik?cik=320193`

## Description
The FMP CIK API is an essential tool for financial professionals, compliance officers, and analysts who need to quickly and accurately retrieve the Central Index Key (CIK) for a specific company. The CIK is a unique identifier used by the U.S. Securities and Exchange Commission (SEC) to track company filings, making it crucial for accessing corporate disclosures and financial data.

Key Features of the CIK API


Quick CIK Lookup: Retrieve a company’s CIK by entering its symbol or name, allowing for efficient access to SEC filings and other regulatory information.
Essential for Compliance: Ensure accurate and timely access to SEC filings for regulatory compliance and corporate governance purposes.
Comprehensive Market Coverage: Search for CIKs across companies listed on major U.S. stock exchanges like NASDAQ and the NYSE.

The CIK API is invaluable for anyone dealing with corporate filings and compliance, providing seamless access to essential company identifiers.

Example: Streamlined SEC Filings: A compliance officer can use the CIK API to quickly find a company’s CIK number and use it to retrieve all relevant SEC filings. This enables efficient monitoring of regulatory disclosures and financial statements.

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
        "320193"
      ],
      [
        "limit",
        "number",
        "50"
      ]
    ]
  }
}
```

## Related API slugs
`search-symbol`, `search-company-screener`, `search-CIK`, `search-ISIN`, `search-name`
