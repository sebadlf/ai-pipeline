# Cash Flow Statement

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/cashflow-statement](https://site.financialmodelingprep.com/developer/docs/stable/cashflow-statement)

Gain insights into a company's cash flow activities with the Cash Flow Statements API. Analyze cash generated and used from operations, investments, and financing activities to evaluate the financial health and sustainability of a business.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/cash-flow-statement?symbol=AAPL`

## Description
The Cash Flow Statements API provides a detailed view of a company's cash flow, giving investors and analysts essential data to understand how a company generates and spends its cash. This API is critical for:


Assessing Financial Health: Evaluate a company’s ability to generate cash from its core operations and its reliance on investments and financing.
Understanding Cash Management: Track cash inflows and outflows from operating, investing, and financing activities to understand how well a company manages its cash resources.
Free Cash Flow Analysis: Analyze free cash flow to determine how much cash a company has left over after paying for capital expenditures, providing a clearer picture of financial flexibility.

This API delivers real-time and historical cash flow data, offering a comprehensive look at how a company manages its cash, which is essential for investment decisions, financial modeling, and credit analysis.

Example Use Case
A financial analyst uses the Cash Flow Statements API to evaluate a company's operating cash flow and free cash flow, helping to assess whether the company can sustain operations, invest in growth, and return value to shareholders.

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
          "Q1",
          "Q2",
          "Q3",
          "Q4",
          "FY",
          "annual",
          "quarter"
        ]
      ]
    ]
  }
}
```

## Related API slugs
`income-statement-growth`, `as-reported-balance-statements`, `financial-reports-form-10-k-xlsx`, `as-reported-income-statements`, `revenue-geographic-segments`
