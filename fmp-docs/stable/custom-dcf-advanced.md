# Custom DCF Advanced

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/custom-dcf-advanced](https://site.financialmodelingprep.com/developer/docs/stable/custom-dcf-advanced)

Run a tailored Discounted Cash Flow (DCF) analysis using the FMP Custom DCF Advanced API. With detailed inputs, this API allows users to fine-tune their assumptions and variables, offering a more personalized and precise valuation for a company.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/custom-discounted-cash-flow?symbol=AAPL`

## Description
The Custom DCF Advanced API is designed for financial analysts and investors who want to customize their DCF analysis based on their specific forecasts and assumptions. This API gives users the flexibility to modify key variables such as revenue growth, EBITDA, capital expenditures, and risk factors to achieve a tailored company valuation. Key features include:


Customizable Inputs: Adjust core financial metrics such as revenue, EBITDA, and capital expenditures to fit your projections and forecasts.
Advanced Financial Assumptions: Modify factors like the risk-free rate, market risk premium, tax rate, and WACC to create a more accurate valuation.
Comprehensive Output: Get detailed results including equity value, free cash flow, terminal value, and equity value per share, all based on your custom inputs.

This API is ideal for professional analysts or advanced users looking to customize DCF models to reflect their investment strategy or valuation assumptions.

Example Use Case
An equity analyst might use the Custom DCF Advanced API to adjust Apple’s financial forecasts, input a different market risk premium, or modify the long-term growth rate. These tailored inputs allow the analyst to create a unique valuation model for the company and make more informed investment decisions.

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
        "revenueGrowthPct",
        "number",
        "0.1094119804597946"
      ],
      [
        "ebitdaPct",
        "number",
        "0.31273548388"
      ],
      [
        "depreciationAndAmortizationPct",
        "number",
        "0.0345531631720999"
      ],
      [
        "cashAndShortTermInvestmentsPct",
        "number",
        "0.2344222126801843"
      ],
      [
        "receivablesPct",
        "number",
        "0.1533770531229388"
      ],
      [
        "inventoriesPct",
        "number",
        "0.0155245674227653"
      ],
      [
        "payablePct",
        "number",
        "0.1614868903169657"
      ],
      [
        "ebitPct",
        "number",
        "0.2781823207138459"
      ],
      [
        "capitalExpenditurePct",
        "number",
        "0.0306025847141713"
      ],
      [
        "operatingCashFlowPct",
        "number",
        "0.2886333485760204"
      ],
      [
        "sellingGeneralAndAdministrativeExpensesPct",
        "number",
        "0.0662854095187211"
      ],
      [
        "taxRate",
        "number",
        "0.14919579658453103"
      ],
      [
        "longTermGrowthRate",
        "number",
        "4"
      ],
      [
        "costOfDebt",
        "number",
        "3.64"
      ],
      [
        "costOfEquity",
        "number",
        "9.51168"
      ],
      [
        "marketRiskPremium",
        "number",
        "4.72"
      ],
      [
        "beta",
        "number",
        "1.244"
      ],
      [
        "riskFreeRate",
        "number",
        "3.64"
      ]
    ]
  }
}
```

## Related API slugs
`dcf-advanced`, `dcf-levered`, `custom-dcf-levered`
