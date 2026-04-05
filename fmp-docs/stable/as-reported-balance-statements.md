# As Reported Balance Statements

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/as-reported-balance-statements](https://site.financialmodelingprep.com/developer/docs/stable/as-reported-balance-statements)

Access balance sheets as reported by the company with the As Reported Balance Statements API. View detailed financial data on assets, liabilities, and equity directly from official filings.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/balance-sheet-statement-as-reported?symbol=AAPL`

## Description
The As Reported Balance Statements API offers unadjusted balance sheet data as reported by companies. It provides insight into a company's financial position, including:


Asset Overview: View cash, receivables, inventory, and long-term assets as reported.
Liability Breakdown: Access current and non-current liabilities, deferred revenues, and more.
Equity Insights: Examine stockholders’ equity, including retained earnings and stock details.

This API is ideal for analysts and investors who want raw, as-reported balance sheet data to perform accurate financial assessments.

Example Use Case
An investment analyst can use the As Reported Balance Statements API to evaluate Apple's asset-liability structure for Q1 2010, helping to understand the company's financial position during that period without any adjustments.

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
        "limit",
        "number",
        "5"
      ],
      [
        "period",
        "string",
        [
          "annual",
          "quarter"
        ]
      ]
    ]
  }
}
```

## Related API slugs
`as-reported-income-statements`, `revenue-product-segmentation`, `financial-reports-form-10-k-xlsx`, `financial-statement-growth`, `financial-reports-form-10-k-json`
