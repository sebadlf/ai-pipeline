# ESG Ratings

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/esg-ratings](https://site.financialmodelingprep.com/developer/docs/stable/esg-ratings)

Access comprehensive ESG ratings for companies and funds with the FMP ESG Ratings API. Make informed investment decisions based on environmental, social, and governance (ESG) performance data.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/esg-ratings?symbol=AAPL`

## Description
The FMP ESG Ratings API provides detailed ESG ratings for companies and funds, helping investors and analysts assess the sustainability and ethical impact of their investments. This API is essential for:


Evaluating ESG Performance: Access ESG ratings that reflect a company’s or fund’s performance across environmental, social, and governance criteria, sourced from corporate sustainability reports, ESG research firms, and government agencies.
Informed Investment Decisions: Use ESG ratings to identify companies and funds that align with your ethical and sustainability goals, ensuring that your investments support positive social and environmental outcomes.
Filtering Based on ESG Scores: Customize your search to filter for companies with high ESG ratings or low ESG controversy scores, helping you focus on organizations that meet your specific ESG criteria.

This API is a valuable tool for socially conscious investors, financial analysts, and asset managers who prioritize ESG factors in their investment strategies.

Examples Use Cases


High ESG Performance: An investor interested in companies with strong ESG practices can filter for those with an ESG rating of 80 or higher, ensuring that their investments align with their values.
Low ESG Controversy: An analyst focused on minimizing environmental risks in their portfolio may filter for companies with low ESG controversy scores, indicating fewer issues related to environmental or social impacts.

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
`esg-search`, `esg-benchmark`
