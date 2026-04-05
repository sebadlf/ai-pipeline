# Equity Offering Updates

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/latest-equity-offering](https://site.financialmodelingprep.com/developer/docs/stable/latest-equity-offering)

Stay informed about the latest equity offerings with the FMP Equity Offering Updates API. Track new shares being issued by companies and get insights into exempt offerings and amendments.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/fundraising-latest?page=0&limit=10`

## Description
The FMP Equity Offering Updates API provides detailed information on newly issued equity securities, including company details, offering amounts, and regulatory filings. This API is a crucial tool for investors, analysts, and market researchers who need to:


Monitor New Equity Issuances: Track companies issuing new shares and stay informed about recent equity offerings.
Analyze Offering Details: Access important data such as filing dates, form types, industry classifications, and the minimum investment required.
Stay Compliant: Get information on exempt offerings under regulations like 06b, 3C, and 3C.1 to assess the legal status of an equity issue.

This API is invaluable for keeping up-to-date with the latest equity issuances, ensuring you never miss an important offering or amendment.

Example Use Case
An institutional investor could use the Equity Offering Updates API to identify new investment opportunities by tracking newly issued equity offerings from companies across various sectors.

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
        "10"
      ],
      [
        "cik",
        "string",
        "0002013736"
      ]
    ]
  }
}
```

## Related API slugs
`crowdfunding-search`, `latest-crowdfunding`, `equity-offering-by-cik`, `crowdfunding-by-cik`, `equity-offering-search`
