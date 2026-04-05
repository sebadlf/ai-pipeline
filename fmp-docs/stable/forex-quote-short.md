# Forex Short Quote

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/forex-quote-short](https://site.financialmodelingprep.com/developer/docs/stable/forex-quote-short)

Quickly access concise forex pair quotes with the Forex Quote Snapshot API. Get a fast look at live currency exchange rates, price changes, and volume in real time.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/quote-short?symbol=EURUSD`

## Description
The Forex Quote Snapshot API is designed for users who need a streamlined view of forex data. It offers a quick, no-frills quote for various currency pairs, making it ideal for fast decision-making in trading environments.


Real-Time Price Data: Instantly retrieve the current price for forex pairs such as EUR/USD.
Brief Overview: Access essential data, including the latest price change and trading volume, in a compact format.
Efficient Monitoring: Ideal for traders and analysts who need fast updates without extensive details.

This API is perfect for quick checks of forex market movements, helping traders stay informed and react promptly.

Example Use Case
A currency trader uses the Forex Quote Snapshot API to monitor the EUR/USD pair throughout the day, quickly checking price changes and volume to make rapid trading decisions.

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
        "EURUSD"
      ]
    ]
  }
}
```

## Related API slugs
`forex-intraday-5-min`, `forex-historical-price-eod-full`, `all-forex-quotes`, `forex-intraday-1-min`, `forex-historical-price-eod-light`
