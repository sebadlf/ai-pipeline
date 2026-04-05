# Crowdfunding By CIK

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/crowdfunding-by-cik](https://site.financialmodelingprep.com/developer/docs/stable/crowdfunding-by-cik)

Access detailed information on all crowdfunding campaigns launched by a specific company with the FMP Crowdfunding By CIK API.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/crowdfunding-offerings?cik=0001916078`

## Description
The FMP Crowdfunding By CIK API provides a comprehensive list of crowdfunding campaigns launched by companies, identified by their Central Index Key (CIK). This endpoint is invaluable for investors and analysts who need to:


Identify Company-Specific Campaigns: Discover all crowdfunding campaigns initiated by companies you are interested in investing in.
Track Crowdfunding Activity Over Time: Monitor the crowdfunding activity of specific companies to identify trends, growth, and changes in their fundraising efforts.
Spot Investment Opportunities: Use the data on crowdfunding campaigns to uncover potential investment opportunities based on the crowdfunding strategies of companies.

This API is essential for those looking to make informed decisions based on the crowdfunding activity of specific companies.

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
        "0001916078"
      ]
    ]
  }
}
```

## Related API slugs
`latest-equity-offering`, `crowdfunding-search`, `equity-offering-search`, `equity-offering-by-cik`, `latest-crowdfunding`
