# Latest Mergers & Acquisitions

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/latest-mergers-acquisitions](https://site.financialmodelingprep.com/developer/docs/stable/latest-mergers-acquisitions)

Access real-time data on the latest mergers and acquisitions with the FMP Latest Mergers and Acquisitions API. This API provides key information such as the transaction date, company names, and links to detailed filing information for further analysis.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/mergers-acquisitions-latest?page=0&limit=100`

## Description
The FMP Latest Mergers and Acquisitions API delivers the most recent information on corporate mergers and acquisitions, giving users access to essential data about company takeovers and transactions. Key features include:


Transaction Details: Get information on the companies involved, including acquiring and targeted firms.
Filing Information: Access official filings and documents from the SEC for a deeper analysis of the deal.
Timely Updates: Stay informed with the most recent mergers and acquisitions data, providing insights into market consolidation.

This API is ideal for analysts, investors, and corporate strategists looking to track corporate activity and make informed decisions based on the latest M&A trends.

Example Use Case
An investment analyst can use the Latest Mergers and Acquisitions API to track recent acquisitions and evaluate the impact of these deals on the companies involved. The data can be used to assess market consolidation, competitive dynamics, and potential investment opportunities.

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
`delisted-companies`, `profile-cik`, `all-shares-float`, `shares-float`, `profile-symbol`
