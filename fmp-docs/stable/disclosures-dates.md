# Fund & ETF Disclosures by Date

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/disclosures-dates](https://site.financialmodelingprep.com/developer/docs/stable/disclosures-dates)

Retrieve detailed disclosures for mutual funds and ETFs based on filing dates with the FMP Fund & ETF Disclosures by Date API. Stay current with the latest filings and track regulatory updates effectively.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/funds/disclosure-dates?symbol=VWO`

## Description
The FMP Fund & ETF Disclosures by Date API allows users to quickly access mutual fund and ETF disclosures by specifying filing dates. This API is essential for:


Tracking Recent Filings: Stay informed about the latest mutual fund and ETF filings by retrieving disclosures based on specific filing dates. This feature is ideal for analysts, investors, and compliance officers looking to stay updated on current regulatory filings.
Historical Research: The API allows users to retrieve disclosures from past quarters or years, making it a valuable tool for historical financial research, performance tracking, and compliance verification.
Monitoring Filing Trends: Regularly reviewing filings by date helps users keep an eye on market trends and understand how recent filings may impact the financial markets.

For example, an investor may want to track all disclosures filed in the second quarter of 2024. By using the Fund & ETF Disclosures by Date API, they can quickly retrieve and review these filings to understand any significant changes in fund strategies or holdings.

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
        "VWO"
      ],
      [
        "cik",
        "string",
        "0000036405"
      ]
    ]
  }
}
```

## Related API slugs
`information`, `country-weighting`, `etf-asset-exposure`, `disclosures-name-search`, `latest-disclosures`
