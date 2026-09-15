"""Load a Trellis-produced forecast JSON into the shapes `engine.DealModel` needs.

`bridge.standalone_year_from_trellis` maps ONE year of a live Trellis forecast dict.
This module handles the other path: a forecast already run, converted to $mm, and
written to disk by `scripts/run_trellis_jnj.py`. Separating the two is deliberate --
the bridge is the live-API seam, this is the file seam, and conflating them would mean
every engine run needed network access to SEC EDGAR.

The validation here is not ceremony. A forecast JSON is the one input to this model
that no human reads before it is used: it is machine-written, then machine-consumed.
That is exactly where a units error (dollars where millions are expected), a silently
truncated year, or a NaN slips through unnoticed and produces a pro-forma bridge that
looks plausible and is wrong by a factor of a million. So the loader refuses anything
it cannot verify rather than coercing it.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from .proforma import StandaloneYear

# A large-cap buyer's annual revenue in USD MILLIONS. Below this, the file is almost
# certainly still in raw dollars (or is billions); above it, something is very wrong.
# Wide on purpose -- this catches magnitude errors, not modelling disagreements.
_PLAUSIBLE_REVENUE_MM = (100.0, 10_000_000.0)


class ForecastLoadError(ValueError):
    pass


def load_standalone_years(path: str | Path,
                          expect_years: int | None = None,
                          check_units: bool = True) -> tuple[StandaloneYear, ...]:
    """Read a forecast JSON into an ordered tuple of StandaloneYear.

    Expected shape, as written by scripts/run_trellis_jnj.py:

        {"1": {"fiscal_year": 2026, "revenue_mm": ..., "operating_income_mm": ...,
               "net_income_mm": ..., "depreciation_amortisation_mm": ...}, "2": {...}}

    The outer key is the FORWARD YEAR INDEX (1 = first full year post-close), not the
    fiscal year -- because that is what the pro-forma engine indexes on. `fiscal_year`
    is carried alongside for traceability and is never used as the index; a model that
    silently reindexed on calendar year would break the moment a forecast started
    somewhere other than year 1.
    """
    path = Path(path)
    if not path.exists():
        raise ForecastLoadError(
            f"{path} not found. Run `python scripts/run_trellis_jnj.py` first -- it "
            f"fetches from SEC EDGAR and writes this file. That needs network access "
            f"to data.sec.gov and TRELLIS_USER_AGENT set.")

    try:
        raw = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        raise ForecastLoadError(f"{path} is not valid JSON: {e}") from e

    if not isinstance(raw, dict) or not raw:
        raise ForecastLoadError(f"{path} must be a non-empty object keyed by year index.")

    try:
        indices = sorted(int(k) for k in raw)
    except ValueError as e:
        raise ForecastLoadError(
            f"{path} has a non-integer top-level key. Keys are forward-year indices "
            f"('1', '2', ...), not fiscal years or labels.") from e

    if indices != list(range(1, len(indices) + 1)):
        raise ForecastLoadError(
            f"{path} year indices are {indices}; expected a contiguous run starting at "
            f"1. A gap here would silently shift every year of the pro-forma bridge.")

    required = ("revenue_mm", "operating_income_mm", "net_income_mm")
    years: list[StandaloneYear] = []
    for i in indices:
        row = raw[str(i)]
        missing = [k for k in required if k not in row]
        if missing:
            raise ForecastLoadError(f"{path} year {i} is missing {missing}.")

        for k, v in row.items():
            if k == "fiscal_year":
                continue
            if not isinstance(v, (int, float)) or isinstance(v, bool):
                raise ForecastLoadError(f"{path} year {i} field '{k}' is not numeric: {v!r}")
            if math.isnan(v) or math.isinf(v):
                raise ForecastLoadError(
                    f"{path} year {i} field '{k}' is {v} -- a non-finite value will "
                    f"propagate silently through the whole pro-forma bridge.")

        rev = float(row["revenue_mm"])
        if check_units and not (_PLAUSIBLE_REVENUE_MM[0] <= rev <= _PLAUSIBLE_REVENUE_MM[1]):
            raise ForecastLoadError(
                f"{path} year {i} revenue_mm is {rev:,.0f}, outside the plausible range "
                f"{_PLAUSIBLE_REVENUE_MM[0]:,.0f}-{_PLAUSIBLE_REVENUE_MM[1]:,.0f} for a "
                f"figure in USD MILLIONS. Most likely the file is still in raw dollars "
                f"(Trellis's native unit) and was not converted at the boundary. Pass "
                f"check_units=False only if you are certain the unit is right.")

        years.append(StandaloneYear(
            year_index=i,
            revenue=rev,
            operating_income=float(row["operating_income_mm"]),
            net_income=float(row["net_income_mm"]),
            depreciation_amortisation=float(row.get("depreciation_amortisation_mm", 0.0)),
        ))

    if expect_years is not None and len(years) != expect_years:
        raise ForecastLoadError(
            f"{path} has {len(years)} years; the model needs {expect_years}. Buyer and "
            f"target forecasts must cover the same horizon -- engine.DealModel rejects "
            f"a mismatch rather than silently dropping the overhang.")

    return tuple(years)


def fiscal_years(path: str | Path) -> tuple[int, ...]:
    """The fiscal years behind a forecast file, for labelling output.

    Kept separate from load_standalone_years because StandaloneYear deliberately does
    not carry a fiscal year -- the engine indexes on forward-year position, and adding
    a calendar field would invite someone to index on it.
    """
    raw = json.loads(Path(path).read_text())
    return tuple(raw[k].get("fiscal_year") for k in sorted(raw, key=int))
