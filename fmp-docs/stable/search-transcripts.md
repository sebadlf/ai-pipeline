# Earnings Transcript

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/search-transcripts](https://site.financialmodelingprep.com/developer/docs/stable/search-transcripts)

Access the full transcript of a company’s earnings call with the FMP Earnings Transcript API. Stay informed about a company’s financial performance, future plans, and overall strategy by analyzing management's communication.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/earning-call-transcript?symbol=AAPL&year=2020&quarter=3`

## Description
The FMP Earnings Transcript API provides complete access to the text transcript of a company’s earnings call. This API is essential for:


In-Depth Financial Analysis: Gain valuable insights into a company’s financial performance by reviewing what executives say during earnings calls. The transcript can provide context and details beyond what’s available in standard financial reports.
Strategic Planning: Learn about a company’s future plans and strategic direction straight from management. Understanding the company’s priorities and challenges can help investors make informed decisions.
Risk Identification: Use the transcript to identify any potential red flags or areas of concern that might not be immediately apparent in the earnings report. This can include management's tone, response to analysts' questions, or any mention of operational or financial difficulties.

Example Use Case
Investor Insight: An investor might use the Earnings Transcript API to review the most recent earnings call for a retail company. By analyzing the transcript, the investor can assess the company’s response to market trends, management’s outlook on upcoming quarters, and any potential risks that were discussed.

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
        "year*",
        "string",
        "2020"
      ],
      [
        "quarter*",
        "string",
        "3"
      ],
      [
        "limit",
        "number",
        "1"
      ]
    ]
  }
}
```

## Related API slugs
`latest-transcripts`, `transcripts-dates-by-symbol`, `available-transcript-symbols`
