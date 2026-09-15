"""The loader guards the one input no human reads before it is used."""
import json

import pytest

from deallab.loader import ForecastLoadError, fiscal_years, load_standalone_years


def _write(tmp_path, data):
    p = tmp_path / "forecast.json"
    p.write_text(json.dumps(data))
    return p


def _good(n=5, revenue_mm=94_000.0):
    return {str(i): {"fiscal_year": 2025 + i, "revenue_mm": revenue_mm * (1.06 ** i),
                     "operating_income_mm": 20_000.0, "net_income_mm": 15_000.0,
                     "depreciation_amortisation_mm": 4_000.0}
            for i in range(1, n + 1)}


def test_loads_a_well_formed_forecast_in_forward_year_order(tmp_path):
    years = load_standalone_years(_write(tmp_path, _good()))
    assert [y.year_index for y in years] == [1, 2, 3, 4, 5]
    assert years[0].revenue < years[-1].revenue


def test_missing_file_names_the_script_that_produces_it(tmp_path):
    with pytest.raises(ForecastLoadError, match="run_trellis_jnj.py"):
        load_standalone_years(tmp_path / "nope.json")


def test_raw_dollars_instead_of_millions_is_caught_not_silently_used(tmp_path):
    """The 1,000,000x error this check exists for -- a forecast left in Trellis's
    native raw-dollar unit would produce a plausible-looking, catastrophically wrong
    pro-forma bridge."""
    p = _write(tmp_path, _good(revenue_mm=94_000_000_000.0))
    with pytest.raises(ForecastLoadError, match="USD MILLIONS"):
        load_standalone_years(p)


def test_unit_check_can_be_disabled_deliberately(tmp_path):
    p = _write(tmp_path, _good(revenue_mm=94_000_000_000.0))
    assert load_standalone_years(p, check_units=False)


def test_a_gap_in_the_year_sequence_is_refused(tmp_path):
    data = _good()
    del data["3"]
    with pytest.raises(ForecastLoadError, match="contiguous run"):
        load_standalone_years(_write(tmp_path, data))


def test_indices_not_starting_at_one_are_refused(tmp_path):
    data = {str(i): _good()["1"] for i in range(2, 5)}
    with pytest.raises(ForecastLoadError, match="contiguous run"):
        load_standalone_years(_write(tmp_path, data))


def test_nan_is_refused_rather_than_propagated(tmp_path):
    data = _good()
    p = tmp_path / "f.json"
    p.write_text(json.dumps(data).replace('"net_income_mm": 15000.0',
                                          '"net_income_mm": NaN'))
    with pytest.raises(ForecastLoadError, match="non-finite"):
        load_standalone_years(p)


def test_missing_required_field_is_named(tmp_path):
    data = _good()
    del data["2"]["net_income_mm"]
    with pytest.raises(ForecastLoadError, match="net_income_mm"):
        load_standalone_years(_write(tmp_path, data))


def test_horizon_mismatch_is_refused_because_the_engine_needs_matched_sides(tmp_path):
    with pytest.raises(ForecastLoadError, match="same horizon"):
        load_standalone_years(_write(tmp_path, _good(n=3)), expect_years=5)


def test_non_integer_keys_are_refused(tmp_path):
    with pytest.raises(ForecastLoadError, match="forward-year indices"):
        load_standalone_years(_write(tmp_path, {"FY2026": _good()["1"]}))


def test_invalid_json_says_so(tmp_path):
    p = tmp_path / "f.json"
    p.write_text("{not json")
    with pytest.raises(ForecastLoadError, match="not valid JSON"):
        load_standalone_years(p)


def test_fiscal_years_are_available_separately_but_never_used_as_the_index(tmp_path):
    """StandaloneYear deliberately carries no fiscal year -- the engine indexes on
    forward position, and a calendar field would invite indexing on it."""
    p = _write(tmp_path, _good())
    assert fiscal_years(p) == (2026, 2027, 2028, 2029, 2030)
    assert not hasattr(load_standalone_years(p)[0], "fiscal_year")
