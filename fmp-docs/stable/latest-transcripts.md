# Latest Earning Transcripts

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/latest-transcripts](https://site.financialmodelingprep.com/developer/docs/stable/latest-transcripts)

Access available earnings transcripts for companies with the FMP Latest Earning Transcripts API. Retrieve a list of companies with earnings transcripts, along with the total number of transcripts available for each company.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/earning-call-transcript-latest`

## Description
The FMP Latest Earning Transcripts API provides users with essential data on the availability of earnings transcripts for various companies. This API is ideal for financial analysts, investors, and researchers looking to track earnings performance over time.


Identify Available Transcripts: Quickly access a list of companies with earnings transcripts, complete with the number of available transcripts for each.
Support Earnings Analysis: Use the transcript count to further analyze earnings call data and gain insights into company performance.
Track Historical Data: Discover companies with multiple transcripts to track earnings calls over different quarters or years.

Example Use Case
An investor looking to analyze a company’s earnings performance over several quarters can use the Earnings Transcript List API to identify companies with multiple earnings call transcripts and retrieve the necessary documents for deeper financial analysis.

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
        "limit",
        "number",
        "100"
      ],
      [
        "page",
        "number",
        "0"
      ]
    ]
  }
}
```

## Related API slugs
`search-transcripts`, `transcripts-dates-by-symbol`, `available-transcript-symbols`
