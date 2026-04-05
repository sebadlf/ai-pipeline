# Earnings Surprises Bulk

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/earnings-surprises-bulk](https://site.financialmodelingprep.com/developer/docs/stable/earnings-surprises-bulk)

The Earnings Surprises Bulk API allows users to retrieve bulk data on annual earnings surprises, enabling quick analysis of which companies have beaten, missed, or met their earnings estimates. This API provides actual versus estimated earnings per share (EPS) for multiple companies at once, offering valuable insights for investors and analysts.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/earnings-surprises-bulk?year=2025`

## Description
The Earnings Surprises Bulk API is an essential tool for those who want to:


Identify Performance Trends: Track whether companies consistently beat or miss earnings estimates.
Investment Opportunities: Spot potential investment opportunities in companies that are exceeding earnings expectations or facing downward trends due to missed estimates.
Analyze Market Sentiment: Gauge investor confidence by analyzing how a company's earnings performance compares to market expectations.
Strategic Forecasting: Use historical data to enhance financial forecasting models or make data-driven investment decisions.

With this bulk API, you can easily retrieve earnings surprises data for multiple companies, simplifying the process of spotting trends across different industries or sectors.

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
        "year*",
        "string",
        "2025"
      ]
    ]
  }
}
```

## Related API slugs
`peers-bulk`, `eod-bulk`, `price-target-summary-bulk`, `balance-sheet-statement-bulk`, `dcf-bulk`
