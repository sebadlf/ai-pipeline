# Form 13F Filings Dates

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/form-13f-filings-dates](https://site.financialmodelingprep.com/developer/docs/stable/form-13f-filings-dates)

The Form 13F Filings Dates API allows you to retrieve dates associated with Form 13F filings by institutional investors. This is crucial for tracking stock holdings of institutional investors at specific points in time, providing valuable insights into their investment strategies.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/institutional-ownership/dates?cik=0001067983`

## Description
The Form 13F Filings Dates API is ideal for users interested in tracking when institutional investors file Form 13F reports with the SEC. This data reveals their stock holdings and investment trends, helping investors and analysts understand what major institutions are investing in during specific quarters.
This API is perfect for:


Investor Monitoring: Track when institutional investors file their stock holdings with the SEC.
Quarterly Analysis: Review changes in institutional holdings across different quarters.
Historical Research: Analyze filing patterns over the years and spot trends in institutional ownership.

This API provides a streamlined way to track the timing of institutional holdings, which is useful for investment analysis and understanding market trends.

Example Use Case
An analyst can use the Form 13F Filings Dates API to check the filing dates of a major institutional investor, allowing them to compare portfolio changes from quarter to quarter and make informed decisions based on institutional behavior.

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
        "0001067983"
      ]
    ]
  }
}
```

## Related API slugs
`industry-summary`, `latest-filings`, `holders-industry-breakdown`, `positions-summary`, `holder-performance-summary`
