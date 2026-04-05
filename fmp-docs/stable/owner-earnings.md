# Owner Earnings

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/owner-earnings](https://site.financialmodelingprep.com/developer/docs/stable/owner-earnings)

Retrieve a company's owner earnings with the Owner Earnings API, which provides a more accurate representation of cash available to shareholders by adjusting net income. This metric is crucial for evaluating a company’s profitability from the perspective of investors.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/owner-earnings?symbol=AAPL`

## Description
The Owner Earnings API offers a detailed breakdown of a company’s cash flow adjusted for key factors, such as capital expenditures and depreciation. It is designed for:


Investor Evaluation: Calculate cash truly available to shareholders, giving a clearer picture of profitability beyond net income.
Valuation Analysis: Use owner earnings to make informed decisions when valuing a company for long-term investments.
Capex Insight: Get insights into both maintenance and growth capital expenditures (Capex) to assess how much of the company’s income is being reinvested.
Owner Earnings Per Share: Track the value available to each share, helping determine if a stock is a good investment.

This API provides a robust view of a company’s profitability and cash flow potential, especially for value investors looking for long-term returns.

Example Use Case
An investor uses the Owner Earnings API to evaluate Apple’s true cash earnings before purchasing additional shares, ensuring that the company’s income aligns with their long-term investment strategy.

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
      ]
    ]
  }
}
```

## Related API slugs
`as-reported-income-statements`, `financial-reports-form-10-k-xlsx`, `as-reported-cashflow-statements`, `metrics-ratios`, `enterprise-values`
