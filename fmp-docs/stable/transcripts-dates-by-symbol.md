# Transcripts Dates By Symbol

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/transcripts-dates-by-symbol](https://site.financialmodelingprep.com/developer/docs/stable/transcripts-dates-by-symbol)

Access earnings call transcript dates for specific companies with the FMP Transcripts Dates By Symbol API. Get a comprehensive overview of earnings call schedules based on fiscal year and quarter.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/earning-call-transcript-dates?symbol=AAPL`

## Description
The FMP Transcripts Dates By Symbol API provides users with precise information about when earnings call transcripts are available for a given company. This API is ideal for investors, analysts, and researchers who want to track earnings discussions and financial insights over time, including:


Earnings Call Availability by Quarter: Retrieve transcript dates by quarter and fiscal year to track a company's performance.
Timely Access to Transcripts: Get access to transcripts for upcoming or historical earnings calls for in-depth analysis.
Comprehensive Coverage: Identify and analyze earnings call transcripts across multiple quarters for better decision-making.

This API is designed to help users stay informed about earnings call schedules and access key financial insights through transcripts from specific periods.

Example Use Case
An investment firm can use the Transcripts Dates By Symbol API to keep track of a company's earnings calls for each quarter and access these transcripts for detailed performance analysis and strategic planning.

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
`latest-transcripts`, `search-transcripts`, `available-transcript-symbols`
