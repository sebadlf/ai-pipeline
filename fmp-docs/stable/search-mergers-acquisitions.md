# Search Mergers & Acquisitions

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/search-mergers-acquisitions](https://site.financialmodelingprep.com/developer/docs/stable/search-mergers-acquisitions)

Search for specific mergers and acquisitions data with the FMP Search Mergers and Acquisitions API. Retrieve detailed information on M&A activity, including acquiring and targeted companies, transaction dates, and links to official SEC filings.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/mergers-acquisitions-search?name=Apple`

## Description
The FMP Search Mergers and Acquisitions API allows users to find mergers and acquisitions by company name, enabling a deeper understanding of corporate activity. This API is useful for those needing detailed data on past and ongoing deals, including:


Company-Specific M&A Data: Search for M&A transactions involving specific companies, either as the acquirer or target.
Transaction Dates: Access the exact dates of the transactions for precise tracking.
Filing Links: Obtain links to official SEC documents for detailed information on the terms and conditions of the deal.

This API is perfect for financial analysts, researchers, and corporate strategists who need comprehensive M&A data to inform business or investment decisions.

Example Use Case
A corporate strategist can use the Search Mergers and Acquisitions API to identify past acquisition targets of a competitor. This information can help shape competitive strategies or identify industry trends that may affect future business opportunities.

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
        "Apple"
      ]
    ]
  }
}
```

## Related API slugs
`profile-symbol`, `latest-mergers-acquisitions`, `company-notes`, `all-shares-float`, `historical-employee-count`
