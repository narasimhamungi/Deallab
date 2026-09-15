import pytest

from deallab import verdict
from deallab.accretion import AccretionResult, BreakevenSynergies


def _acc(year, adj, gaap):
    return AccretionResult(
        year_index=year, standalone_eps=5.0,
        gaap_pro_forma_eps=5.0 * (1 + gaap), adjusted_pro_forma_eps=5.0 * (1 + adj),
        gaap_delta_eps=5.0 * gaap, adjusted_delta_eps=5.0 * adj,
        gaap_pct=gaap, adjusted_pct=adj, attribution={},
        purchase_accounting_gap_eps=5.0 * (adj - gaap))


def _breakeven(required=100.0, identified=50.0):
    return BreakevenSynergies(1, "adjusted", required * 0.8, required, identified,
                              required - identified, 0.1, "test reading")


def test_deal_verdict_exposes_no_combined_score():
    """The refusal to merge the lenses is the design, so it is worth a test."""
    v = verdict.build(
        verdict.build_accounting_verdict([_acc(1, 0.03, -0.01)], _breakeven()),
        verdict.build_economic_verdict(16_600.0, 12_000.0, "DCF mid", 1_000.0))
    for banned in ("score", "overall", "recommendation_score", "verdict_score"):
        assert not hasattr(v, banned)


def test_unexplained_premium_is_price_less_standalone_less_synergy_npv():
    e = verdict.build_economic_verdict(
        price_paid=16_600.0, standalone_value=12_000.0,
        standalone_basis="DCF mid", synergy_npv=1_000.0)
    assert e.premium_paid == pytest.approx(4_600.0)
    assert e.unexplained_premium == pytest.approx(3_600.0)
    assert "not been articulated" in e.reading


def test_synergies_covering_the_premium_is_named_as_the_strongest_case():
    e = verdict.build_economic_verdict(16_600.0, 12_000.0, "DCF mid", synergy_npv=5_000.0)
    assert e.unexplained_premium < 0
    assert "does not require benefits nobody has named" in e.reading


def test_no_fit_standalone_value_declines_to_state_a_premium():
    e = verdict.build_economic_verdict(
        16_600.0, None, "every method disqualified", synergy_npv=1_000.0)
    assert e.premium_paid is None
    assert "cannot be answered" in e.reading


def test_accretive_but_unexplained_premium_is_named_as_the_value_destroying_quadrant():
    v = verdict.build(
        verdict.build_accounting_verdict([_acc(1, 0.04, 0.01)], _breakeven()),
        verdict.build_economic_verdict(16_600.0, 12_000.0, "DCF mid", 500.0))
    assert "goodwill impairment" in v.disagreement


def test_dilutive_but_economically_covered_is_named_as_the_proceed_quadrant():
    v = verdict.build(
        verdict.build_accounting_verdict([_acc(1, -0.03, -0.05)], _breakeven()),
        verdict.build_economic_verdict(16_600.0, 12_000.0, "DCF mid", 6_000.0))
    assert "economics are the decision" in v.disagreement


def test_agreement_between_lenses_is_not_treated_as_confirmation():
    v = verdict.build(
        verdict.build_accounting_verdict([_acc(1, 0.04, 0.02)], _breakeven()),
        verdict.build_economic_verdict(16_600.0, 12_000.0, "DCF mid", 6_000.0))
    assert "not independent confirmation" in v.disagreement


def test_first_accretive_year_is_identified_across_the_horizon():
    a = verdict.build_accounting_verdict(
        [_acc(1, -0.02, -0.05), _acc(2, 0.00, -0.03), _acc(3, 0.04, 0.01)],
        _breakeven())
    assert a.first_accretive_year == 3


def test_never_accretive_is_stated_rather_than_left_blank():
    a = verdict.build_accounting_verdict(
        [_acc(1, -0.02, -0.05), _acc(2, -0.01, -0.04)], _breakeven())
    assert a.first_accretive_year is None
    assert "Never adjusted-accretive" in a.format()


def test_irr_below_wacc_reinforces_the_economic_reading():
    e = verdict.build_economic_verdict(16_600.0, 12_000.0, "DCF mid", 500.0,
                                       irr=0.05, wacc=0.08)
    assert "shortfall of IRR against WACC" in e.reading
