# Stock Peer Comparison

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/peers](https://site.financialmodelingprep.com/developer/docs/stable/peers)

Identify and compare companies within the same sector and market capitalization range using the FMP Stock Peer Comparison API. Gain insights into how a company stacks up against its peers on the same exchange.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/stock-peers?symbol=AAPL`

## Description
The FMP Stock Peer Comparison API provides a curated list of companies that trade on the same exchange, belong to the same sector, and have a similar market capitalization. This API is essential for:


Competitive Analysis: Use the API to compare a company’s performance against its peers. This comparison can help you identify companies that are outperforming or underperforming within their sector.
Sector-Specific Insights: By focusing on companies within the same sector and market cap range, investors can obtain a more relevant and accurate comparison, making it easier to assess relative performance and market positioning.
Investment Strategy: Investors can use this information to refine their investment strategy by identifying strong performers within a sector or by finding undervalued companies that have the potential to grow.

This API is a valuable resource for investors seeking to conduct in-depth competitive analysis and to make informed decisions based on how a company compares to its peers.

Example Use Case
Performance Benchmarking: An investor might use the Stock Peer Comparison API to compare the revenue growth and earnings per share (EPS) of a technology company to those of its peers within the same sector. This can help the investor determine whether the company is a leader in its field or if it lags behind its competitors.

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
`historical-employee-count`, `company-notes`, `profile-cik`, `market-cap`, `company-executives`
