# ETF Sector Weighting

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/sector-weighting](https://site.financialmodelingprep.com/developer/docs/stable/sector-weighting)

The FMP ETF Sector Weighting API provides a breakdown of the percentage of an ETF's assets that are invested in each sector. For example, an investor may want to invest in an ETF that has a high exposure to the technology sector if they believe that the technology sector is poised for growth.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/etf/sector-weightings?symbol=SPY`

## Description
The FMP ETF Sector Allocation API provides crucial information about the distribution of an ETF’s assets across different sectors. This API is particularly useful for investors who want to:


Analyze Sector Exposure: Gain insights into how an ETF’s assets are allocated across sectors, such as technology, healthcare, or consumer staples, to understand its risk profile.
Identify Sector-Focused ETFs: Find ETFs with significant exposure to sectors that align with your investment thesis. For instance, you might choose an ETF with a high allocation to the technology sector if you expect strong growth in that area.
Diversify Portfolios: Use sector weighting data to diversify your portfolio by selecting ETFs that provide exposure to sectors where you might be under-invested, helping to balance overall risk.

For example, an investor who already has significant exposure to technology stocks might seek out an ETF with substantial holdings in healthcare or consumer staples to diversify their investments and mitigate sector-specific risks.

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
        "SPY"
      ]
    ]
  }
}
```

## Related API slugs
`holdings`, `disclosures-name-search`, `mutual-fund-disclosures`, `etf-asset-exposure`, `country-weighting`
