# Full Forex Quote

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/full-forex-quotes](https://site.financialmodelingprep.com/developer/docs/stable/full-forex-quotes)

Retrieve real-time quotes for multiple forex currency pairs with the FMP Batch Forex Quote API. Get real-time price changes and updates for a variety of forex pairs in a single request.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/batch-forex-quotes`

## Description
The FMP Batch Forex Quote API allows users to track real-time exchange rates for multiple currency pairs at once. This API is ideal for those who need to monitor numerous forex pairs simultaneously. Key features include:


Multiple Currency Pair Tracking: Retrieve real-time quotes for several forex pairs in one request, streamlining market analysis.
Comprehensive Forex Data: Access up-to-date prices, price changes, and trading volumes across a wide range of global currencies.
Efficient Market Monitoring: Ideal for traders or analysts monitoring multiple currency pairs in fast-moving forex markets.

The Batch Forex Quote API is a powerful tool for tracking global forex market trends and staying informed on price fluctuations for multiple pairs.

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
`batch-aftermarket-trade`, `full-mutualfund-quotes`, `quote-change`, `batch-quote`, `aftermarket-trade`
