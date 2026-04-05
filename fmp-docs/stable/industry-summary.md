# Industry Performance Summary

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/industry-summary](https://site.financialmodelingprep.com/developer/docs/stable/industry-summary)

The Industry Performance Summary API provides an overview of how various industries are performing financially. By analyzing the value of industries over a specific period, this API helps investors and analysts understand the health of entire sectors and make informed decisions about sector-based investments.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/institutional-ownership/industry-summary?year=2023&quarter=3`

## Description
The Industry Performance Summary API enables users to retrieve financial performance summaries for specific industries. This API is ideal for:


Sector Analysis: Gain insights into how industries are performing, helping you identify strong or underperforming sectors.
Comparative Industry Health: Compare the financial health of different industries to assess which sectors might present better investment opportunities.
Macro-Level Market Insights: Use industry-level performance data to make informed decisions about broad market trends and economic shifts.

This API offers a macroeconomic view of sector performance, making it a valuable tool for financial analysts, investors, and economists looking to understand industry-specific trends. It is a key tool for understanding industry trends and comparing the financial health of various sectors in the market.

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
        "year*",
        "string",
        "2023"
      ],
      [
        "quarter*",
        "string",
        "3"
      ]
    ]
  }
}
```

## Related API slugs
`form-13f-filings-dates`, `holders-industry-breakdown`, `filings-extract`, `latest-filings`, `filings-extract-with-analytics-by-holder`
