# 1-Hour Interval Index Price

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/index-intraday-1-hour](https://site.financialmodelingprep.com/developer/docs/stable/index-intraday-1-hour)

Access 1-hour interval intraday data for stock indexes using the Intraday 1-Hour Price Data API. This API provides detailed price movements and volume within hourly intervals, making it ideal for tracking medium-term market trends during the trading day.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/historical-chart/1hour?symbol=^GSPC`

## Description
The FMP Intraday 1-Hour Price Data API delivers hourly price data for stock indexes, allowing analysts and traders to track market trends and price movements throughout the day. With open, high, low, and close prices for each hour, this API is suited for those monitoring medium-term intraday performance. Key features include:


Hourly Interval Data: Retrieve open, high, low, and close prices for stock indexes at 1-hour intervals throughout the trading day.
Track Medium-Term Movements: Perfect for traders and analysts interested in observing trends within hourly windows rather than minute-by-minute fluctuations.
Volume Data: Analyze hourly trading volumes to gain insights into market activity and liquidity.
Intraday Trading Support: Ideal for swing traders and medium-term strategies that require detailed data without overwhelming granularity.

This API is particularly useful for traders, analysts, and portfolio managers who need to assess market behavior within hourly intervals to inform their trading decisions.

Example Use Case
A swing trader using the Intraday 1-Hour Price Data API monitors the S&P 500 index (^GSPC) to observe price movements across several trading hours. With hourly updates, they can identify emerging trends and adjust their positions without the need to track minute-by-minute fluctuations.

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
        "^GSPC"
      ],
      [
        "from",
        "date",
        "2024-01-01"
      ],
      [
        "to",
        "date",
        "2024-03-01"
      ]
    ]
  }
}
```

## Related API slugs
`historical-sp-500`, `nasdaq`, `index-quote-short`, `index-quote`, `all-index-quotes`
