# Economics Indicators

**Source:** [https://site.financialmodelingprep.com/developer/docs/stable/economics-indicators](https://site.financialmodelingprep.com/developer/docs/stable/economics-indicators)

Access real-time and historical economic data for key indicators like GDP, unemployment, and inflation with the FMP Economic Indicators API. Use this data to measure economic performance and identify growth trends.

## Endpoint URLs
- `https://financialmodelingprep.com/stable/economic-indicators?name=GDP`

## Description
The FMP Economic Indicators API provides comprehensive access to real-time and historical data for a wide range of economic indicators, including GDP, unemployment rates, and inflation. These indicators are essential tools for:


Economic Performance Tracking: Economic indicators such as GDP, unemployment, and inflation provide a snapshot of the overall health of the economy. By tracking these indicators over time, investors and analysts can gauge economic performance and make predictions about future economic conditions.
Trend Identification: Identifying trends in economic growth is crucial for making informed investment decisions. The Economic Indicators API allows users to analyze historical data and detect patterns that can indicate economic expansion or contraction.
Informed Investment Decisions: Economic data is a key factor in making informed investment decisions. By understanding the current state of the economy and its trajectory, investors can better align their portfolios with economic cycles.

Example Investor Use Case
An investor might use the Economic Indicators API to monitor GDP growth rates over the past decade. By analyzing this data, the investor can identify periods of strong economic growth and align their investment strategy accordingly.

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
        "name*",
        "string",
        [
          "GDP",
          "realGDP",
          "nominalPotentialGDP",
          "realGDPPerCapita",
          "federalFunds",
          "CPI",
          "inflationRate",
          "inflation",
          "retailSales",
          "consumerSentiment",
          "durableGoods",
          "unemploymentRate",
          "totalNonfarmPayroll",
          "initialClaims",
          "industrialProductionTotalIndex",
          "newPrivatelyOwnedHousingUnitsStartedTotalUnits",
          "totalVehicleSales",
          "retailMoneyFunds",
          "smoothedUSRecessionProbabilities",
          "3MonthOr90DayRatesAndYieldsCertificatesOfDeposit",
          "commercialBankInterestRateOnCreditCardPlansAllAccounts",
          "30YearFixedRateMortgageAverage",
          "15YearFixedRateMortgageAverage",
          "tradeBalanceGoodsAndServices"
        ]
      ],
      [
        "from",
        "date",
        "2024-12-09"
      ],
      [
        "to",
        "date",
        "2025-12-09"
      ]
    ]
  }
}
```

## Related API slugs
`treasury-rates`, `economics-calendar`, `market-risk-premium`
