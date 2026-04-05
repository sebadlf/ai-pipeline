# Mutual Fund & ETF Disclosure Name Search

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/disclosures-name-search](https://site.financialmodelingprep.com/developer/docs/stable/disclosures-name-search)

Easily search for mutual fund and ETF disclosures by name using the Mutual Fund & ETF Disclosure Name Search API. This API allows you to find specific reports and filings based on the fund or ETF name, providing essential details like CIK number, entity information, and reporting file number.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/funds/disclosure-holders-search?name=Federated Hermes Government Income Securities, Inc.`

## Description
The Mutual Fund & ETF Disclosure Name Search API helps users quickly locate disclosure documents for mutual funds and ETFs by searching with a specific fund name. It returns critical data such as the fund's symbol, CIK, class information, and the address of the reporting entity. Ideal for investors, analysts, and researchers looking for detailed disclosure information for compliance, research, or investment decision-making.


Fund Name Search: Look up disclosures for mutual funds and ETFs using the fund or entity name.
Key Filing Details: Get important information like CIK number, series and class IDs, entity name, and reporting file number.
Comprehensive Results: The API returns address details and filing information for the searched fund or ETF entity, making it easy to locate relevant documents.

This API is perfect for anyone conducting due diligence or research on mutual funds and ETFs, allowing for precise and efficient disclosure searches.

Example Use Case
A financial analyst can use the Mutual Fund & ETF Disclosure Name Search API to retrieve specific disclosures for a mutual fund by entering its name, helping the analyst review relevant regulatory filings and reports for the fund.

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
        "Federated Hermes Government Income Securities, Inc."
      ]
    ]
  }
}
```

## Related API slugs
`information`, `country-weighting`, `disclosures-dates`, `sector-weighting`, `mutual-fund-disclosures`
