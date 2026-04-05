# Revenue Geographic Segments

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/revenue-geographic-segments](https://site.financialmodelingprep.com/developer/docs/stable/revenue-geographic-segments)

Access detailed revenue breakdowns by geographic region with the Revenue Geographic Segments API. Analyze how different regions contribute to a company’s total revenue and identify key markets for growth.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/revenue-geographic-segmentation?symbol=AAPL`

## Description
The Revenue Geographic Segments API allows users to retrieve revenue data segmented by geographical regions, helping investors and analysts understand the performance of a company in different markets. This API is ideal for:


Regional Revenue Analysis: Break down revenue contributions by geographical area to see which regions are driving growth.
Market Performance Insights: Analyze how a company is performing in key regions like the Americas, Europe, and Greater China.
Global Strategy Planning: For businesses, understanding geographic revenue distribution can help in developing regional strategies and identifying new opportunities for expansion.

This API offers a granular view of regional revenue, making it easier to track a company’s global financial performance.

Example Use Case
An investor can use the Revenue Geographic Segments API to track Apple’s performance across key regions like the Americas, Europe, and Greater China, helping to identify emerging markets or regions with declining sales.

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
      ],
      [
        "period",
        "string",
        [
          "annual",
          "quarter"
        ]
      ],
      [
        "structure",
        "string",
        "flat"
      ]
    ]
  }
}
```

## Related API slugs
`key-metrics-ttm`, `key-metrics`, `owner-earnings`, `metrics-ratios-ttm`, `financial-reports-form-10-k-json`
