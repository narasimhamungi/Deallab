"""Integration against the REAL ValuationLab and Trellis packages, not mocks.

If ValuationLab is not installed these skip. They are the tests that prove the seam
works against the actual upstream API rather than against an assumption about it.
"""
import pytest

vl_triangulate = pytest.importorskip("valuationlab.triangulate")
vl_precedent = pytest.importorskip("valuationlab.precedent")

from deallab.bridge import (
    precedent_check,
    standalone_value,
    standalone_year_from_trellis,
)

Method = vl_triangulate.Method
MethodRange = vl_triangulate.MethodRange


def _range(method, low, mid, high, caveat="none stated"):
    return MethodRange(method=method, low=low, mid=mid, high=high,
                       basis="test basis", caveat=caveat, provenance="test")


def test_standalone_value_uses_valuationlabs_own_anchor_recommendation():
    c = vl_triangulate.triangulate([
        _range(Method.DCF, 90.0, 100.0, 110.0),
        _range(Method.TRADING_COMPS, 95.0, 105.0, 115.0),
    ], terminal_value_share=0.55, comps_multiple_spread=0.3, comps_peer_count=8)
    sv = standalone_value(c)
    assert sv.fit is True
    assert sv.enterprise_value == pytest.approx(
        next(r.mid for r in c.ranges if r.method is c.anchor_method))


def test_a_stated_anchor_is_honoured_over_the_derived_one():
    c = vl_triangulate.triangulate(
        [_range(Method.DCF, 90.0, 100.0, 110.0),
         _range(Method.TRADING_COMPS, 40.0, 200.0, 400.0)],
        anchor=Method.DCF, reasoning="DCF is the only method with a defensible peer set",
        terminal_value_share=0.55)
    assert standalone_value(c).enterprise_value == pytest.approx(100.0)


def test_no_fit_method_returns_unfit_rather_than_falling_back_to_a_midpoint():
    """The upstream disqualification must survive the bridge. Reaching past it for a
    number anyway would undo the whole point of ValuationLab's anchor logic."""
    c = vl_triangulate.triangulate(
        [_range(Method.DCF, 10.0, 100.0, 400.0),
         _range(Method.TRADING_COMPS, 10.0, 100.0, 500.0)],
        terminal_value_share=0.95, comps_multiple_spread=3.8, comps_peer_count=2)
    sv = standalone_value(c)
    if sv.fit:
        pytest.skip("upstream thresholds did not disqualify this construction")
    assert sv.enterprise_value is None
    assert "disqualified" in sv.basis.lower()


def test_precedent_check_refuses_a_list_of_deals():
    """ValuationLab measured that pooling pharma precedents is wrong. A function that
    accepted a list would immediately be used to average one."""
    with pytest.raises(TypeError, match="Pooling precedent"):
        precedent_check(vl_precedent.MATURE_REVENUE_DEALS, 16_600.0, 1_032.0)


def test_precedent_check_compares_against_exactly_one_cited_deal():
    check = precedent_check(vl_precedent.JNJ_ACTELION_2017,
                            subject_ev=16_600.0, subject_revenue=1_032.0)
    assert check.subject_ev_revenue == pytest.approx(16_600.0 / 1_032.0)
    assert check.deal_ev_revenue == pytest.approx(vl_precedent.JNJ_ACTELION_2017.ev_revenue)
    assert "sec.gov" in check.source


def test_two_precedents_run_separately_give_materially_different_readings():
    """Running it twice and reading both is the intended use -- and reproduces the
    upstream finding that no single pharma multiple exists."""
    a = precedent_check(vl_precedent.JNJ_ACTELION_2017, 16_600.0, 1_032.0)
    b = precedent_check(vl_precedent.BMY_CELGENE_2019, 16_600.0, 1_032.0)
    assert abs(a.revenue_multiple_gap - b.revenue_multiple_gap) > 1.0


def test_trellis_forecast_year_maps_onto_the_pro_forma_input_shape():
    year = {"revenue": 1_000.0, "operating_income": 200.0, "net_income": 150.0,
            "depreciation_amortization": 50.0, "capex": 40.0}
    sy = standalone_year_from_trellis(year, year_index=1)
    assert (sy.revenue, sy.operating_income, sy.net_income) == (1_000.0, 200.0, 150.0)
    assert sy.depreciation_amortisation == 50.0


def test_a_missing_trellis_canonical_name_raises_rather_than_zeroing_the_line():
    with pytest.raises(KeyError, match="operating_income"):
        standalone_year_from_trellis({"revenue": 1.0, "net_income": 1.0}, 1)
