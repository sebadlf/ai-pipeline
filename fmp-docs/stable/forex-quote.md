# Forex Quote

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/forex-quote](https://site.financialmodelingprep.com/developer/docs/stable/forex-quote)

Access real-time forex quotes for currency pairs with the Forex Quote API. Retrieve up-to-date information on exchange rates and price changes to help monitor market movements.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/quote?symbol=EURUSD`

## Description
The Forex Quote API provides live exchange rate data for various currency pairs, delivering essential insights for traders and financial analysts. Here’s how it can help you:


Live Forex Quotes: Get up-to-the-minute exchange rates and price updates for different forex pairs, such as EUR/USD.
Detailed Price Information: Access key data, including the current price, day’s high and low, year’s high and low, and percentage changes.
Monitor Market Movements: Track the opening and closing prices, as well as 50-day and 200-day moving averages, to gain a comprehensive view of market trends.

This API is essential for forex traders and financial professionals who need accurate and timely currency exchange data to make informed decisions.

Example Use Case
A forex trader uses the Forex Quote API to monitor the EUR/USD exchange rate throughout the day. By tracking live price changes and percentage movements, the trader can time their trades and react quickly to market fluctuations.

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
`forex-historical-price-eod-full`, `forex-historical-price-eod-light`, `forex-intraday-5-min`, `forex-list`, `forex-quote-short`
