# Search Insider Trades by Reporting Name

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/search-reporting-name](https://site.financialmodelingprep.com/developer/docs/stable/search-reporting-name)

Search for insider trading activity by reporting name using the Search Insider Trades by Reporting Name API. Track trading activities of specific individuals or groups involved in corporate insider transactions.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/insider-trading/reporting-name?name=Zuckerberg`

## Description
The FMP Search Insider Trades by Reporting Name API allows users to search for insider trading activities based on the name of a specific individual or group. This API provides key information such as the reporting CIK (Central Index Key) and the individual’s name associated with insider transactions, enabling users to monitor the trading activity of high-profile individuals or corporate executives. Key features include:


Name-Specific Searches: Easily search for insider trades by entering the name of a specific individual or entity.
Reporting CIK Information: Retrieve the reporting CIK for more in-depth tracking of insider activity across filings.
Track High-Profile Insiders: Monitor trades by well-known corporate executives, directors, or other insiders.
Direct Access to Relevant Data: Quickly find information related to specific individuals’ insider trading activities, with links to more detailed data.

This API is ideal for investors, analysts, and financial researchers who want to track insider trading activities associated with specific people or entities.

Example Use Case
A financial analyst uses the Search Insider Trades by Reporting Name API to track insider trading activity for Mark Zuckerberg. By retrieving the reporting CIK and related transactions, the analyst can monitor Zuckerberg’s trading behavior and analyze how his actions might influence market sentiment regarding Meta Platforms.

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
        "Zuckerberg"
      ]
    ]
  }
}
```

## Related API slugs
`all-transaction-types`, `latest-insider-trade`, `acquisition-ownership`, `search-insider-trades`, `insider-trade-statistics`
