# Startup operating model

ARR bridge, burn, runway and unit economics for an early-stage SaaS business,
in about 250 lines of Python with the workbook generated from it.

The question a founder actually asks is "how long have I got, and what is the
one lever that changes it". Everything here is built backwards from that.

## What it answers

On the illustrative drivers checked into the file:

```
Runway 6.8 months on trailing three month burn.
Below the 9 month mark, so this is a raise-or-cut decision, not a monitoring one.
Cash goes negative in month 8 on the current plan.
CAC payback 31.3 months on first month sales and marketing load.
A 10% adverse move in collection lag takes runway to 5.9 months, -0.9.
A 10% adverse move in opex per month takes runway to 6.1 months, -0.7.
```

The last two lines are the point. Ranking the levers by a uniform 10% adverse
move means the ranking reflects the levers rather than the size of the shock
each one happened to be given. Here collection lag outranks opex, which is the
sort of thing that only shows up if you rank them.

## Run it

```
python3 -I operating_model.py                        # self-check
python3 -I operating_model.py out.xlsx               # Monthly + Summary sheets
```

No dependencies for the model itself. `openpyxl` only for the workbook.

## What it does

- **ARR bridge** per month: opening, new, expansion, contraction, churn, closing
- **Revenue** on the average book over the month, not the opening or closing balance
- **Cash** with a collection lag, so revenue and cash are not treated as the same event
- **Runway** on the trailing three month net burn, so one month of timing noise
  does not move the number a board reads
- **CAC payback** from the sales and marketing share of opex
- **Sensitivity** ranked worst first, filtered to moves that shift runway by at
  least 5%, because a sensitivity table nobody can act on is decoration

## Why you can trust the arithmetic

`python3 -I operating_model.py` runs 13 assertions. They check that:

- the ARR bridge closes in **every** month, not just in total
- ARR and cash both roll forward, each month's opening equal to last month's close
- the cash bridge closes: opening less net burn equals closing
- collections lag by exactly the stated number of months
- zero burn gives infinite runway rather than a divide-by-zero
- tripling churn reduces ARR and cannot increase runway
- the sensitivity table is deterministic, ordered worst first, and no adverse
  shock ever improves runway
- CAC payback does **not** move when the same spend and ARR are split across a
  different number of logos, which is correct rather than a bug, and does
  worsen when sales and marketing load doubles or gross margin halves

That last one started as a failing assertion. The first version asserted that
halving the logo count should lengthen payback. It does not: with total spend
and total new ARR fixed, each logo becomes twice as expensive and twice as
valuable and the two cancel. The assertion was wrong, not the model, so it was
replaced with one that pins the cancellation.

## Scope

The drivers are illustrative, not any real company's. Deliberately absent: a
409A valuation, a cap table, a DCF. A seed or Series A founder does not need
those from an outside analyst, and producing them unasked is how a model gets
filed under "nice chart".

Built by Arpita Tiwari. Bengaluru.
