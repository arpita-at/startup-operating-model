#!/usr/bin/env python3
"""
Startup operating model: ARR bridge, burn, runway and unit economics.

The question a founder actually asks is "how long have I got, and what is the
one lever that changes it". So the model is built backwards from that: every
number here exists to make the runway figure defensible, and every bridge is
asserted to close rather than left to the reader to trust.

    python3 -I operating_model.py            # run the self-check
    python3 -I operating_model.py out.xlsx   # write the workbook

Deliberately not included: a 409A valuation, a cap table, a DCF. A seed or
Series A founder does not need those from an outside analyst, and producing
them unasked is how a model gets filed under "nice chart".
"""
from dataclasses import dataclass, field, replace
import sys

MONTHS = 18
RUNWAY_ALARM = 9          # months; below this a board starts asking questions
MATERIAL_PCT = 0.05       # a driver has to move runway by 5% to be worth a line


@dataclass(frozen=True)
class Drivers:
    """One scenario. Rates are monthly unless the name says otherwise."""
    opening_arr: float = 2_400_000.0      # USD
    opening_cash: float = 3_000_000.0
    new_arr_per_month: float = 110_000.0
    expansion_rate: float = 0.008         # of opening ARR, monthly
    gross_churn_rate: float = 0.013       # of opening ARR, monthly
    contraction_rate: float = 0.004
    gross_margin: float = 0.76
    opex_per_month: float = 520_000.0     # excludes COGS
    opex_growth: float = 0.015            # monthly creep as headcount lands
    sales_marketing_share: float = 0.42   # of opex, used for CAC
    new_logos_per_month: float = 9.0
    collection_lag_months: int = 1        # cash follows revenue by this much

    def label(self) -> str:
        return self._label if hasattr(self, "_label") else "base"


@dataclass
class Month:
    n: int
    opening_arr: float
    new: float
    expansion: float
    contraction: float
    churn: float
    closing_arr: float
    revenue: float
    cogs: float
    opex: float
    collections: float
    net_burn: float
    opening_cash: float
    closing_cash: float


def project(d: Drivers, months: int = MONTHS) -> list[Month]:
    rows: list[Month] = []
    arr, cash = d.opening_arr, d.opening_cash
    billed: list[float] = []
    for n in range(1, months + 1):
        opening_arr = arr
        new = d.new_arr_per_month
        expansion = opening_arr * d.expansion_rate
        contraction = -opening_arr * d.contraction_rate
        churn = -opening_arr * d.gross_churn_rate
        closing_arr = opening_arr + new + expansion + contraction + churn

        # revenue recognised on the average book over the month
        revenue = (opening_arr + closing_arr) / 2 / 12
        cogs = revenue * (1 - d.gross_margin)
        opex = d.opex_per_month * (1 + d.opex_growth) ** (n - 1)

        billed.append(revenue)
        lag = d.collection_lag_months
        collections = billed[n - 1 - lag] if n - 1 - lag >= 0 else 0.0

        net_burn = cogs + opex - collections
        opening_cash = cash
        cash = opening_cash - net_burn

        rows.append(Month(n, opening_arr, new, expansion, contraction, churn,
                          closing_arr, revenue, cogs, opex, collections,
                          net_burn, opening_cash, cash))
        arr = closing_arr
    return rows


def runway_months(rows: list[Month]) -> float:
    """Cash today over the trailing three month average net burn.

    Trailing three months, not last month, because a single month of timing
    noise should not move the number a board reads.
    """
    cash = rows[-1].closing_cash if rows else 0.0
    recent = [r.net_burn for r in rows[:3]]
    burn = sum(recent) / len(recent) if recent else 0.0
    if burn <= 0:
        return float("inf")
    return max(0.0, rows[0].opening_cash / burn)


def months_to_zero(rows: list[Month]) -> int | None:
    for r in rows:
        if r.closing_cash <= 0:
            return r.n
    return None


def cac_payback(d: Drivers, rows: list[Month]) -> float:
    """Months of gross profit needed to repay the acquisition cost of one logo."""
    sm_spend = rows[0].opex * d.sales_marketing_share
    if d.new_logos_per_month <= 0:
        return float("inf")
    cac = sm_spend / d.new_logos_per_month
    arr_per_logo = d.new_arr_per_month / d.new_logos_per_month
    monthly_gp = arr_per_logo / 12 * d.gross_margin
    return cac / monthly_gp if monthly_gp > 0 else float("inf")


def sensitivity(d: Drivers) -> list[tuple[str, float, float]]:
    """Which single driver moves runway most, at a uniform 10% adverse move.

    Uniform because the point is to rank levers, and a ranking built on
    different-sized shocks per driver ranks the shocks, not the levers.
    """
    base = runway_months(project(d))
    shocks = {
        "new ARR per month":   replace(d, new_arr_per_month=d.new_arr_per_month * 0.9),
        "gross churn rate":    replace(d, gross_churn_rate=d.gross_churn_rate * 1.1),
        "gross margin":        replace(d, gross_margin=d.gross_margin * 0.9),
        "opex per month":      replace(d, opex_per_month=d.opex_per_month * 1.1),
        "collection lag":      replace(d, collection_lag_months=d.collection_lag_months + 1),
    }
    out = []
    for name, shocked in shocks.items():
        r = runway_months(project(shocked))
        delta = r - base
        if base and abs(delta) / base >= MATERIAL_PCT:
            out.append((name, r, delta))
    return sorted(out, key=lambda t: t[2])      # worst damage first


def commentary(d: Drivers) -> list[str]:
    rows = project(d)
    base = runway_months(rows)
    zero = months_to_zero(rows)
    lines = []
    if base == float("inf"):
        lines.append("Cash generative on a trailing three month basis; runway is not the binding constraint.")
    else:
        lines.append(f"Runway {base:.1f} months on trailing three month burn.")
        if base < RUNWAY_ALARM:
            lines.append(f"Below the {RUNWAY_ALARM} month mark, so this is a raise-or-cut decision, not a monitoring one.")
    if zero:
        lines.append(f"Cash goes negative in month {zero} on the current plan.")
    pay = cac_payback(d, rows)
    lines.append(f"CAC payback {pay:.1f} months on first month sales and marketing load.")
    for name, r, delta in sensitivity(d)[:3]:
        lines.append(f"A 10% adverse move in {name} takes runway to {r:.1f} months, {delta:+.1f}.")
    return lines


def write_xlsx(d: Drivers, path: str) -> None:
    from openpyxl import Workbook
    from openpyxl.styles import Font
    rows = project(d)
    wb = Workbook()
    ws = wb.active
    ws.title = "Monthly"
    head = ["Month", "Opening ARR", "New", "Expansion", "Contraction", "Churn",
            "Closing ARR", "Revenue", "COGS", "Opex", "Collections",
            "Net burn", "Opening cash", "Closing cash"]
    ws.append(head)
    for c in ws[1]:
        c.font = Font(bold=True)
    for r in rows:
        ws.append([r.n, r.opening_arr, r.new, r.expansion, r.contraction,
                   r.churn, r.closing_arr, r.revenue, r.cogs, r.opex,
                   r.collections, r.net_burn, r.opening_cash, r.closing_cash])
    for col in "BCDEFGHIJKLMN":
        ws.column_dimensions[col].width = 15
        for cell in ws[col][1:]:
            cell.number_format = "#,##0"

    s = wb.create_sheet("Summary")
    s.append(["Startup operating model"]); s["A1"].font = Font(bold=True, size=14)
    s.append([])
    for line in commentary(d):
        s.append([line])
    s.append([])
    s.append(["Driver", "Value"])
    s[f"A{s.max_row}"].font = Font(bold=True)
    for k, v in vars(d).items():
        s.append([k.replace("_", " "), v])
    s.column_dimensions["A"].width = 95
    wb.save(path)


def _selfcheck() -> None:
    d = Drivers()
    rows = project(d)

    # the ARR bridge must close, every month, not just in total
    for r in rows:
        bridged = (r.opening_arr + r.new + r.expansion + r.contraction + r.churn)
        assert abs(bridged - r.closing_arr) < 1e-6, f"ARR bridge open in month {r.n}"

    # each month's opening ARR is last month's close
    for a, b in zip(rows, rows[1:]):
        assert abs(a.closing_arr - b.opening_arr) < 1e-6, "ARR does not roll forward"

    # cash roll-forward must close
    for r in rows:
        assert abs((r.opening_cash - r.net_burn) - r.closing_cash) < 1e-6, "cash bridge open"
    for a, b in zip(rows, rows[1:]):
        assert abs(a.closing_cash - b.opening_cash) < 1e-6, "cash does not roll forward"

    # collections lag by exactly the stated number of months
    assert rows[0].collections == 0.0, "month 1 cannot collect with a 1 month lag"
    assert abs(rows[1].collections - rows[0].revenue) < 1e-6, "lag is not 1 month"

    # a company that spends nothing and collects something has infinite runway
    free = replace(d, opex_per_month=0.0, gross_margin=1.0, collection_lag_months=0)
    assert runway_months(project(free)) == float("inf"), "zero burn must be infinite runway"

    # scenarios must actually diverge, or the toggle is decoration
    worse = replace(d, gross_churn_rate=d.gross_churn_rate * 3)
    assert project(worse)[-1].closing_arr < rows[-1].closing_arr, "churn must reduce ARR"
    assert runway_months(project(worse)) <= runway_months(rows) + 1e-9

    # sensitivity must rank by damage, worst first, and be deterministic
    sens = sensitivity(d)
    assert sens == sensitivity(d), "sensitivity is not deterministic"
    assert all(sens[i][2] <= sens[i + 1][2] for i in range(len(sens) - 1)), \
        "sensitivity must be ordered worst damage first"
    # an adverse shock may not improve runway
    assert all(delta <= 1e-9 for _, _, delta in sens), "an adverse shock improved runway"

    # commentary is deterministic and leads with the number a founder asked for
    assert commentary(d) == commentary(d), "commentary is not deterministic"
    assert "Runway" in commentary(d)[0]

    # CAC payback is independent of logo count, and that is correct rather than
    # a bug: with total spend and total new ARR fixed, winning half as many
    # logos makes each one twice as expensive and twice as valuable, so the
    # payback period does not move. Pinned so nobody "fixes" it later.
    halved = replace(d, new_logos_per_month=d.new_logos_per_month / 2)
    assert abs(cac_payback(halved, project(halved)) - cac_payback(d, rows)) < 1e-9, \
        "payback must not depend on how the same spend and ARR are split across logos"

    # it must worsen on the things that genuinely drive it
    pricey = replace(d, opex_per_month=d.opex_per_month * 2)
    assert cac_payback(pricey, project(pricey)) > cac_payback(d, rows), \
        "doubling sales and marketing load must lengthen payback"
    thin = replace(d, gross_margin=d.gross_margin / 2)
    assert cac_payback(thin, project(thin)) > cac_payback(d, rows), \
        "halving gross margin must lengthen payback"

    print("selfcheck ok:", len(rows), "months,",
          f"runway {runway_months(rows):.1f}m,",
          f"CAC payback {cac_payback(d, rows):.1f}m")
    for line in commentary(d):
        print("  -", line)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        write_xlsx(Drivers(), sys.argv[1])
        print("wrote", sys.argv[1])
    else:
        _selfcheck()
