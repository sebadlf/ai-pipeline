# All Index Quotes

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/all-index-quotes](https://site.financialmodelingprep.com/developer/docs/stable/all-index-quotes)

The All Index Quotes API provides real-time quotes for a wide range of stock indexes, from major market benchmarks to niche indexes. This API allows users to track market performance across multiple indexes in a single request, giving them a broad view of the financial markets.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/batch-index-quotes`

## Description
The All Index Quotes API enables users to retrieve up-to-date quotes for all available stock indexes, including real-time data for both major and minor indexes. This API is ideal for traders, analysts, and investors who need a quick overview of market movements across various indexes without making multiple requests. Key features include:


Real-Time Data: Receive real-time quotes for stock indexes, helping users stay informed about market changes.
Broad Market Coverage: Access data for major indexes like the S&P 500, Dow Jones, NASDAQ, and more specialized or regional indexes.
Simplified Data Retrieval: Retrieve quotes for multiple indexes in a single API call, streamlining data collection for market analysis.

This API is designed for users looking for a comprehensive view of stock index movements, from major global benchmarks to smaller, region-specific indexes.

Example Use Case
A financial analyst tracking global market performance can use the All Index Quotes API to retrieve real-time quotes for multiple stock indexes, such as the S&P 500, FTSE 100, and Nikkei 225, in one request, providing a holistic view of current market trends.

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
`index-historical-price-eod-full`, `index-historical-price-eod-light`, `nasdaq`, `historical-nasdaq`, `historical-dow-jones`
