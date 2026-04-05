# Financial Reports Form 10-K JSON

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/financial-reports-form-10-k-json](https://site.financialmodelingprep.com/developer/docs/stable/financial-reports-form-10-k-json)

Access comprehensive annual reports with the FMP Annual Reports on Form 10-K API. Obtain detailed information about a company’s financial performance, business operations, and risk factors as reported to the SEC.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/financial-reports-json?symbol=AAPL&year=2022&period=FY`

## Description
The FMP Annual Reports on Form 10-K API provides investors, analysts, and researchers with direct access to the annual reports that public companies in the United States are required to file with the Securities and Exchange Commission (SEC). This API is an invaluable resource for:


In-Depth Financial Analysis: Access detailed financial statements and data included in a company's Form 10-K to evaluate its financial health and performance over the past fiscal year.
Understanding Business Operations: Gain insights into a company’s operations, including its business strategy, key markets, and operational challenges, as disclosed in the Form 10-K.
Assessing Risk Factors: Review the risk factors section of the Form 10-K to understand the potential challenges and uncertainties that a company faces, helping to inform your investment decisions.

The FMP Annual Reports on Form 10-K API makes it easy to retrieve and analyze these comprehensive reports, providing a complete picture of a company's financial and operational status.

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
        "AAPL"
      ],
      [
        "year*",
        "number",
        "2022"
      ],
      [
        "period*",
        "string",
        [
          "Q1",
          "Q2",
          "Q3",
          "Q4",
          "FY"
        ]
      ]
    ]
  }
}
```

## Related API slugs
`financial-reports-form-10-k-xlsx`, `financial-scores`, `key-metrics-ttm`, `metrics-ratios`, `balance-sheet-statement`
