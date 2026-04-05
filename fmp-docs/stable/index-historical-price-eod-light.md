# Historical Index Light Chart

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/index-historical-price-eod-light](https://site.financialmodelingprep.com/developer/docs/stable/index-historical-price-eod-light)

Retrieve end-of-day historical prices for stock indexes using the Historical Price Data API. This API provides essential data such as date, price, and volume, enabling detailed analysis of price movements over time.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/historical-price-eod/light?symbol=^GSPC`

## Description
The FMP Historical Price Data API allows users to access end-of-day price data for stock indexes, offering insights into historical performance. By tracking this data, analysts can better understand market trends, volatility, and stock index movements. Key features include:


Comprehensive Price Data: Retrieve historical prices for key stock indexes, including data on closing price, date, and trading volume.
Supports Multiple Indexes: Access data for a wide range of stock indexes from various global markets.
Detailed Volume Information: Track trading volume for each index, offering insights into market activity levels.
Historical Performance Analysis: Analyze past price movements to identify trends, patterns, and potential investment opportunities.

This API is particularly useful for financial analysts, investors, and market researchers who need accurate historical data to assess stock index performance over time.

Example Use Case
An investment analyst is developing a historical trend analysis for the S&P 500 index (^GSPC). By using the Historical Price Data API, they can retrieve end-of-day prices for specific dates, analyze the volume and price movements over time, and present findings to their clients for more informed investment decisions.

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
        "2025-09-09"
      ],
      [
        "to",
        "date",
        "2025-12-09"
      ]
    ]
  }
}
```

## Related API slugs
`historical-nasdaq`, `index-intraday-5-min`, `nasdaq`, `indexes-list`, `dow-jones`
