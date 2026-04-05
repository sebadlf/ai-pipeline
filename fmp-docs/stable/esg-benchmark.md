# ESG Benchmark Comparison

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/esg-benchmark](https://site.financialmodelingprep.com/developer/docs/stable/esg-benchmark)

Evaluate the ESG performance of companies and funds with the FMP ESG Benchmark Comparison API. Compare ESG leaders and laggards within industries to make informed and responsible investment decisions.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/esg-benchmark`

## Description
The FMP ESG Benchmark Comparison API allows investors and analysts to compare the Environmental, Social, and Governance (ESG) performance of companies and funds against their peers. This powerful tool helps you:


Identify ESG Leaders: Find companies and funds that excel in ESG performance by comparing them to industry peers.
Spot ESG Laggards: Identify companies that fall behind in ESG performance, allowing you to make informed decisions about where to allocate your investments.
Monitor ESG Improvements: Track companies that are making significant strides in their ESG ratings, signaling positive change and potential investment opportunities.

Example Use Cases


For Investors: Filter for companies in the top 10% of their industry in ESG ratings to focus on industry leaders in sustainable practices.
For Analysts: Search for companies that have shown a significant increase in their ESG rating over the past year to identify those making notable improvements in their ESG performance.

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
        "year",
        "string",
        "2023"
      ]
    ]
  }
}
```

## Related API slugs
`esg-search`, `esg-ratings`
