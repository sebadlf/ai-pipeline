# CIK List

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/cik-list](https://site.financialmodelingprep.com/developer/docs/stable/cik-list)

Access a comprehensive database of CIK (Central Index Key) numbers for SEC-registered entities with the FMP CIK List API. This endpoint is essential for businesses, financial professionals, and individuals who need quick access to CIK numbers for regulatory compliance, financial transactions, and investment research.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/cik-list?page=0&limit=1000`

## Description
The FMP CIK List API provides an extensive and searchable database of CIK numbers assigned to SEC-registered entities. A CIK number serves as a unique identifier required for many regulatory filings and financial transactions, making it a crucial tool for:

 


Investment Research: Gain insights into institutional investment patterns through CIK-linked 13F filings, helping you understand equity holdings and market sentiment.
Regulatory Compliance: Easily retrieve CIK numbers to ensure compliance with SEC regulations and reporting requirements.
Portfolio Management: Track the CIK numbers of key institutional investors, allowing for enhanced portfolio management and market analysis.

This API is an invaluable resource for anyone involved in the financial industry, including investment analysts, portfolio managers, and compliance officers, providing access to the CIK numbers that underpin many SEC filings.

Example: A portfolio manager can use the CIK List API to retrieve the CIK number of an institutional investor from recent 13F filings, allowing them to analyze the investor’s equity holdings and make informed portfolio decisions.

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
        "page",
        "number",
        "0"
      ],
      [
        "limit",
        "number",
        "1000"
      ]
    ]
  }
}
```

## Related API slugs
`available-industries`, `available-exchanges`, `company-symbols-list`, `available-sectors`, `earnings-transcript-list`
