# Company Profile by CIK

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/profile-cik](https://site.financialmodelingprep.com/developer/docs/stable/profile-cik)

Retrieve detailed company profile data by CIK (Central Index Key) with the FMP Company Profile by CIK API. This API allows users to search for companies using their unique CIK identifier and access a full range of company data, including stock price, market capitalization, industry, and much more.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/profile-cik?cik=320193`

## Description
The FMP Company Profile by CIK API provides comprehensive company information for users who want to look up firms using the CIK code. Ideal for compliance officers, analysts, and investors, this API allows access to vital company details based on their CIK number. Key features include:


Company Lookup by CIK: Easily find companies using their Central Index Key for fast and accurate identification.
Stock Price & Market Cap: Get the most up-to-date stock price and market capitalization data for the requested company.
Comprehensive Financial Data: Access essential financial metrics like beta, dividend yield, and trading range to evaluate a company's performance.
Global Identifiers: Retrieve key identifiers such as CIK, ISIN, and CUSIP to streamline cross-platform tracking of companies.
Company Information: Get in-depth details on the company's business operations, CEO, sector, and contact information.
IPO & Industry Data: View company industry, sector, and IPO details to better understand its market position.

Example Use Case
A compliance officer conducting a regulatory review can use the Company Profile by CIK API to quickly retrieve comprehensive data on Apple Inc. using its unique CIK number, ensuring accuracy in cross-referencing the company across different databases.

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
      ]
    ]
  }
}
```

## Related API slugs
`historical-employee-count`, `executive-compensation-benchmark`, `company-notes`, `search-mergers-acquisitions`, `market-cap`
