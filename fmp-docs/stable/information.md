# ETF & Mutual Fund Information

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/information](https://site.financialmodelingprep.com/developer/docs/stable/information)

Access comprehensive data on ETFs and mutual funds with the FMP ETF & Mutual Fund Information API. Retrieve essential details such as ticker symbol, fund name, expense ratio, assets under management, and more.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/etf/info?symbol=SPY`

## Description
The FMP ETF & Mutual Fund Information API offers a detailed look into the financial and structural information of ETFs and mutual funds. This API enables investors to:


Compare Funds: Evaluate different ETFs and mutual funds by reviewing key metrics like ticker symbol, name, expense ratio, and assets under management to choose the most cost-effective and suitable investment options.
Identify Investment Opportunities: Use the detailed data to discover ETFs and mutual funds that align with your specific investment strategy, risk tolerance, and financial goals.
Understand Investment Objectives: Learn more about the objectives and strategies of various ETFs and mutual funds, helping you assess their suitability for inclusion in your portfolio based on asset class, sector exposure, and expense ratios.

For example, an investor can use this API to compare the expense ratios of various ETFs and mutual funds, find funds with large assets under management, or analyze sector weightings to ensure their investments align with their market outlook.

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
        "SPY"
      ]
    ]
  }
}
```

## Related API slugs
`etf-asset-exposure`, `latest-disclosures`, `country-weighting`, `sector-weighting`, `holdings`
