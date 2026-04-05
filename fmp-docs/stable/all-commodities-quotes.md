# All Commodities Quotes

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/all-commodities-quotes](https://site.financialmodelingprep.com/developer/docs/stable/all-commodities-quotes)

Access real-time quotes for multiple commodities at once with the FMP Real-Time Batch Commodities Quotes API. Instantly track price changes, volume, and other key metrics for a broad range of commodities.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/batch-commodity-quotes`

## Description
The FMP Real-Time Batch Commodities Quotes API allows users to retrieve live price data for a wide selection of commodities in one request. This API is designed for investors, traders, and analysts who need to monitor several commodities simultaneously and make quick, informed decisions based on real-time market information.


Batch Quotes: Retrieve quotes for multiple commodities in a single API call, simplifying the process of tracking a wide range of assets.
Real-Time Updates: Get up-to-the-minute pricing, ensuring you’re always working with the most current market data.
Market Metrics: Access additional metrics such as price changes and trading volume to provide context to market movements.

This API is essential for professionals who need efficient access to commodity prices without having to query each asset individually.

You can use this API to simultaneously retrieve the latest price for commodities such as DCUSD (current price: $22.29, change: -0.2, volume: 284), allowing for fast analysis and comparison of market data.

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
`commodities-historical-price-eod-light`, `commodities-intraday-1-min`, `commodities-historical-price-eod-full`, `commodities-list`, `commodities-quote-short`
