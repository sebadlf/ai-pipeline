# Stock Grades

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/grades](https://site.financialmodelingprep.com/developer/docs/stable/grades)

Access the latest stock grades from top analysts and financial institutions with the FMP Grades API. Track grading actions, such as upgrades, downgrades, or maintained ratings, for specific stock symbols, providing valuable insight into how experts evaluate companies over time.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/grades?symbol=AAPL`

## Description
The FMP Grades API offers timely data on stock evaluations by prominent financial institutions, including:


Grading Company: Identify the institution providing the stock rating.
Previous Grade and New Grade: View the change in grade, if any, from previous assessments to the latest one.
Action Taken: Determine whether the grade was upgraded, downgraded, or maintained.
Date of Evaluation: See when the latest grading action occurred.

This API helps investors and analysts understand the latest sentiment from financial experts, enabling better investment decisions based on how stocks are graded.

Example Use Case
An investor can use the Grades API to track the latest stock ratings for their portfolio, seeing how financial institutions view the company's current performance and investment potential.

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
`grades-summary`, `historical-ratings`, `historical-grades`, `price-target-consensus`, `financial-estimates`
