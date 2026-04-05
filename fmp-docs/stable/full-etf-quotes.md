# ETF Price Quotes

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/full-etf-quotes](https://site.financialmodelingprep.com/developer/docs/stable/full-etf-quotes)

Get real-time price quotes for exchange-traded funds (ETFs) with the FMP ETF Price Quotes API. Track current prices, performance changes, and key data for a wide variety of ETFs.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/batch-etf-quotes`

## Description
The FMP ETF Price Quotes API allows investors to access real-time pricing information and performance updates for ETFs. This API is essential for those looking to:


Monitor ETF Performance: Stay updated on the latest prices and performance metrics of different ETFs.
Evaluate Investment Opportunities: Use real-time price data to assess the value of ETFs and make informed investment decisions.
Compare ETFs: Easily track and compare the performance of multiple ETFs to optimize your portfolio strategy.

This API provides comprehensive information for investors and analysts looking to make data-driven decisions regarding their ETF investments.

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
        "short",
        "boolean",
        "true"
      ]
    ]
  }
}
```

## Related API slugs
`aftermarket-trade`, `quote-short`, `aftermarket-quote`, `batch-aftermarket-trade`, `full-mutualfund-quotes`
