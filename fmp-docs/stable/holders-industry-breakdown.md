# Holders Industry Breakdown

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/holders-industry-breakdown](https://site.financialmodelingprep.com/developer/docs/stable/holders-industry-breakdown)

The Holders Industry Breakdown API provides an overview of the sectors and industries that institutional holders are investing in. This API helps analyze how institutional investors distribute their holdings across different industries and track changes in their investment strategies over time.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/institutional-ownership/holder-industry-breakdown?cik=0001067983&year=2023&quarter=3`

## Description
The Holders Industry Breakdown API allows users to retrieve data on the industries institutional investors are focusing on, including the weight of their holdings in each sector and how that weight changes over time. This API provides detailed insights into the industry allocation of institutional investors, making it easier to understand their sector focus and strategy.


Industry Focus Analysis: Understand which industries are receiving the most investment from major institutional holders.
Portfolio Diversification: Analyze how diversified institutional investors' portfolios are across different sectors.
Investment Trend Insights: Track changes in the weight of industry holdings to identify shifts in institutional investment strategies.

This API is ideal for investors, analysts, and portfolio managers looking to gain insights into institutional investment behavior across various industries.

Example Use Case
A financial analyst can use the Holders Industry Breakdown API to analyze Berkshire Hathaway's sector focus, identifying whether they are increasing or decreasing their exposure to industries like technology or healthcare over time.

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
      ],
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
`filings-extract`, `latest-filings`, `filings-extract-with-analytics-by-holder`, `form-13f-filings-dates`, `holder-performance-summary`
