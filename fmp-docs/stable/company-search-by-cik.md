# SEC Filings Company Search By CIK

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/company-search-by-cik](https://site.financialmodelingprep.com/developer/docs/stable/company-search-by-cik)

Easily find company information using a CIK (Central Index Key) with the FMP SEC Filings Company Search By CIK API. Access essential company details and filings linked to a specific CIK number.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/sec-filings-company-search/cik?cik=0000320193`

## Description
The FMP SEC Filings Company Search By CIK API enables users to search for a company’s regulatory filings and corporate information based on its unique Central Index Key (CIK). This API is ideal for:


CIK-Based Search: Input a company’s CIK number to retrieve corporate data and access its SEC filings.
Comprehensive Company Information: Retrieve details such as company name, CIK number, SIC code, business address, and phone number.
Access to SEC Filings: Instantly access the latest SEC filings for companies, allowing for thorough financial research and corporate tracking.

This API is particularly useful for investors, analysts, and compliance professionals who need to gather detailed company information and filing history using a CIK number.

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
        "0000320193"
      ]
    ]
  }
}
```

## Related API slugs
`company-search-by-symbol`, `financials-latest`, `industry-classification-search`, `all-industry-classification`, `8k-latest`
