# Aftermarket Trade

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/aftermarket-trade](https://site.financialmodelingprep.com/developer/docs/stable/aftermarket-trade)

Track real-time trading activity occurring after regular market hours with the FMP Aftermarket Trade API. Access key details such as trade prices, sizes, and timestamps for trades executed during the post-market session.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/aftermarket-trade?symbol=AAPL`

## Description
The FMP Aftermarket Trade API allows investors to monitor trades made outside of standard market hours, offering insights into post-market trading activity. This API is ideal for:


After-Hours Monitoring: Stay informed about stock prices and trading activity in the aftermarket session to track price movements outside the main trading day.
Investor Insights: Detect trends or patterns in aftermarket trades that could provide valuable information ahead of the next trading session.
Enhanced Trading Strategies: Use aftermarket data to adjust trading strategies for the next day or make more informed decisions based on overnight market activity.

This API helps users gain visibility into the post-market period, enabling more comprehensive tracking of market activity outside traditional trading hours.

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
`full-forex-quotes`, `full-mutualfund-quotes`, `aftermarket-quote`, `full-cryptocurrency-quotes`, `batch-aftermarket-quote`
