# Revenue Product Segmentation

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/revenue-product-segmentation](https://site.financialmodelingprep.com/developer/docs/stable/revenue-product-segmentation)

Access detailed revenue breakdowns by product line with the Revenue Product Segmentation API. Understand which products drive a company's earnings and get insights into the performance of individual product segments.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/revenue-product-segmentation?symbol=AAPL`

## Description
The Revenue Product Segmentation API provides a comprehensive breakdown of a company’s revenue by product, making it easy to analyze performance across different product categories. This API is ideal for:


Product-Specific Revenue Analysis: Understand how much each product contributes to the company’s total earnings.
Strategic Insights: Gain insights into the growth or decline of specific product segments to inform investment decisions or corporate strategy.
Competitive Benchmarking: Compare product segment revenues across different companies in the same industry to gauge market position.

This API offers a detailed view of product-level revenue, helping users identify growth drivers and track the financial health of specific product lines.

Example Use Case
An investor can use the Revenue Product Segmentation API to see how much of Apple’s earnings come from iPhone sales compared to other products, such as Macs or wearables.

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
`financial-scores`, `as-reported-financial-statements`, `metrics-ratios-ttm`, `key-metrics-ttm`, `metrics-ratios`
