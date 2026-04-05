# Latest Crowdfunding Campaigns

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/latest-crowdfunding](https://site.financialmodelingprep.com/developer/docs/stable/latest-crowdfunding)

Discover the most recent crowdfunding campaigns with the FMP Latest Crowdfunding Campaigns API. Stay informed on which companies and projects are actively raising funds, their financial details, and offering terms.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/crowdfunding-offerings-latest?page=0&limit=100`

## Description
The FMP Latest Crowdfunding Campaigns API provides detailed information on current crowdfunding campaigns, including the names of issuers, offering types, and financial data. This API is essential for investors, analysts, and platforms that want to track the latest crowdfunding activity.


Track Crowdfunding Campaigns: Access the most up-to-date information on crowdfunding campaigns, including company names, funding goals, and offering types.
Detailed Financial Information: View key financial metrics such as total assets, cash equivalents, debt, and net income for each company running a crowdfunding campaign.
Company Backgrounds: Get insights into the legal status and jurisdiction of the companies, including the number of employees and other relevant organizational data.

This API is a valuable tool for those looking to follow new crowdfunding opportunities, assess potential investments, or stay up to date on market trends in the crowdfunding space.

Example Use Case
An investor can use the Crowdfunding Campaigns API to review the financial health and offering details of various crowdfunding campaigns, helping them evaluate potential opportunities and diversify their portfolio.

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
        "100"
      ]
    ]
  }
}
```

## Related API slugs
`crowdfunding-by-cik`, `latest-equity-offering`, `crowdfunding-search`, `equity-offering-by-cik`, `equity-offering-search`
