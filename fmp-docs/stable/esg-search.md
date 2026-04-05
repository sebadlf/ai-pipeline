# ESG Investment Search

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/esg-search](https://site.financialmodelingprep.com/developer/docs/stable/esg-search)

Align your investments with your values using the FMP ESG Investment Search API. Discover companies and funds based on Environmental, Social, and Governance (ESG) scores, performance, controversies, and business involvement criteria.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/esg-disclosures?symbol=AAPL`

## Description
The FMP ESG Investment Search API is designed to help investors find companies and funds that align with their Environmental, Social, and Governance (ESG) values. This powerful tool allows you to:


Search by ESG Scores: Identify companies and funds with strong ESG ratings that meet your investment criteria.
Evaluate Performance: Filter investments based on their ESG performance to ensure they align with your values and financial goals.
Assess Controversies: Avoid investments in companies involved in significant ESG controversies by filtering based on controversy scores.
Apply Business Involvement Screens: Screen companies and funds based on specific business activities or sectors that align with your ESG principles.

Examples Use Cases


An investor focused on sustainability might search for companies with an ESG scores of 80 or higher to ensure strong environmental and social practices.
An investor concerned about environmental impact could search for companies with low ESG controversy scores to avoid potential risks.

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
`esg-ratings`, `esg-benchmark`
