# Exchange Stock Quotes

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/full-exchange-quotes](https://site.financialmodelingprep.com/developer/docs/stable/full-exchange-quotes)

Retrieve real-time stock quotes for all listed stocks on a specific exchange with the FMP Exchange Stock Quotes API. Track price changes and trading activity across the entire exchange.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/batch-exchange-quote?exchange=NASDAQ`

## Description
The FMP Exchange Stock Quotes API allows users to access real-time quotes for all stocks trading on a specific exchange. This API is crucial for:


Comprehensive Exchange Monitoring: Track every stock listed on a particular exchange, providing a complete view of the market activity.
Real-Time Trading Data: Access up-to-date price quotes, volume, and change information for all stocks, allowing you to monitor trading trends.
Portfolio Management: Compare performance across multiple stocks on the same exchange to make well-informed investment decisions.

This API is ideal for investors, analysts, and traders who need an overview of trading activity and stock performance on a specific exchange.

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
        "exchange*",
        "string",
        "NASDAQ"
      ],
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
`quote-short`, `quote`, `batch-aftermarket-quote`, `batch-quote-short`, `full-cryptocurrency-quotes`
