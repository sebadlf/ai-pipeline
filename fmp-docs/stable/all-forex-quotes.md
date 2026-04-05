# Batch Forex Quotes

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/all-forex-quotes](https://site.financialmodelingprep.com/developer/docs/stable/all-forex-quotes)

Easily access real-time quotes for multiple forex pairs simultaneously with the Batch Forex Quotes API. Stay updated on global currency exchange rates and monitor price changes across different markets.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/batch-forex-quotes`

## Description
The Batch Forex Quotes API enables users to retrieve live forex quotes for numerous currency pairs in a single request, streamlining the process of monitoring multiple forex pairs at once.


Track Global Exchange Rates: Get real-time prices for a wide range of currency pairs from around the world.
Bulk Data Retrieval: Receive real-time forex quotes for multiple pairs, including price, change, and volume, in one request.
Ideal for High-Frequency Traders: Perfect for traders and analysts who need to monitor many currency pairs quickly and efficiently.

This API simplifies the process of keeping tabs on the global forex market, making it easy to track exchange rates and price fluctuations in real time.

Example Use Case
A forex trader uses the Batch Forex Quotes API to retrieve quotes for 50 different currency pairs at once, helping them monitor price movements and volume across global currencies in real time.

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
`forex-intraday-1-min`, `forex-intraday-5-min`, `forex-historical-price-eod-light`, `forex-intraday-1-hour`, `forex-quote-short`
