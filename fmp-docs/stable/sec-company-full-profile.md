# SEC Company Full Profile

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/sec-company-full-profile](https://site.financialmodelingprep.com/developer/docs/stable/sec-company-full-profile)

Retrieve detailed company profiles, including business descriptions, executive details, contact information, and financial data with the FMP SEC Company Full Profile API.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/sec-profile?symbol=AAPL`

## Description
The FMP SEC Company Full Profile API offers comprehensive data on companies registered with the SEC. This API is ideal for:


Detailed Company Profiles: Access in-depth information on a company's operations, SIC code, CEO, fiscal year, and employee count.
Executive and Contact Information: Retrieve key executive details and contact information, including business and mailing addresses, phone numbers, and website links.
Company Description and Operations: Get a detailed company description, including its products, services, markets, and business sectors, allowing for a full understanding of its operations.
Financial and Regulatory Data: This API provides essential financial data like fiscal year end, IPO date, and links to SEC filings.

This API is crucial for investors, analysts, and researchers who need detailed corporate profiles for financial analysis, competitive research, and investment decision-making.

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
        "symbol*",
        "string",
        "AAPL"
      ],
      [
        "cik-A",
        "string",
        "320193"
      ]
    ]
  }
}
```

## Related API slugs
`8k-latest`, `all-industry-classification`, `company-search-by-symbol`, `search-by-cik`, `company-search-by-cik`
