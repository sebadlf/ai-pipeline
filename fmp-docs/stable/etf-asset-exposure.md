# ETF Asset Exposure

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/etf-asset-exposure](https://site.financialmodelingprep.com/developer/docs/stable/etf-asset-exposure)

Discover which ETFs hold specific stocks with the FMP ETF Asset Exposure API. Access detailed information on market value, share numbers, and weight percentages for assets within ETFs.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/etf/asset-exposure?symbol=AAPL`

## Description
The FMP ETF Asset Exposure API provides detailed data on the exposure of individual stocks within various ETFs. This API is essential for:


Identifying ETF Holdings: Find out which ETFs hold a particular stock, along with details such as market value, the number of shares held, and the weight percentage of the stock within the ETF.
Analyzing Asset Exposure: Use the data to analyze the exposure of specific assets within ETFs, helping you understand how widely a stock is held and its significance within different funds.
Informed Investment Decisions: Investors can leverage this information to assess the popularity and weight of a stock across multiple ETFs, guiding their decisions on buying or selling the stock based on its representation in the market.

This API is a valuable resource for investors who want to explore the relationship between stocks and ETFs, particularly for understanding the broader market sentiment towards a specific asset.

Example Use Cases
ETF Research: An investor interested in Apple Inc. (AAPL) can use the ETF Asset Exposure API to find all ETFs that hold AAPL shares. The investor can then analyze the weight of AAPL within each ETF to determine which funds are most heavily invested in the stock.

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
      ]
    ]
  }
}
```

## Related API slugs
`disclosures-name-search`, `latest-disclosures`, `information`, `country-weighting`, `sector-weighting`
