# Crowdfunding Campaign Search

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/crowdfunding-search](https://site.financialmodelingprep.com/developer/docs/stable/crowdfunding-search)

Search for crowdfunding campaigns by company name, campaign name, or platform with the FMP Crowdfunding Campaign Search API. Access detailed information to track and analyze crowdfunding activities.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/crowdfunding-offerings-search?name=enotap`

## Description
The FMP Crowdfunding Campaign Search API allows users to search for crowdfunding campaigns based on company name, campaign name, or platform. This API is a valuable tool for investors and analysts who need to:


Find Specific Campaigns: Quickly access information on specific crowdfunding campaigns, including the amount raised, number of backers, and investment deadlines.
Track Company Activity: Monitor the crowdfunding activity of particular companies to identify trends or patterns over time.
Identify Investment Opportunities: Use crowdfunding data to discover potential investment opportunities based on recent and ongoing campaigns.

This API provides comprehensive details about crowdfunding campaigns, enabling users to make informed decisions based on up-to-date information.

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
        "name*",
        "string",
        "enotap"
      ]
    ]
  }
}
```

## Related API slugs
`equity-offering-by-cik`, `crowdfunding-by-cik`, `latest-equity-offering`, `latest-crowdfunding`, `equity-offering-search`
