import pytest
from fixtures import CITE, terms

from deallab.provenance import AssumptionRegister, assumed, sourced
from deallab.terms import ContingentValueRight


def test_upfront_price_excludes_the_cvr():
    t = terms()
    assert t.upfront_equity_purchase_price() == pytest.approx(100.00 * 50.0)


def test_cvr_is_probability_weighted_not_taken_at_maximum():
    """Booking a CVR at its cap assumes every milestone hits; booking it at zero
    pretends it isn't consideration. Neither is ASC 805."""
    t = terms()
    assert t.contingent_consideration_fair_value() == pytest.approx(10.00 * 0.40 * 50.0)
    assert t.total_equity_purchase_price() == pytest.approx(5_000.0 + 200.0)


def test_deal_without_a_cvr_has_zero_contingent_consideration():
    assert terms(with_cvr=False).contingent_consideration_fair_value() == 0.0


def test_cvr_weight_outside_zero_to_one_is_rejected():
    cvr = ContingentValueRight(
        max_per_share=sourced("m", 35.0, CITE),
        probability_weight=assumed("w", 1.4, CITE), milestones="x")
    with pytest.raises(ValueError, match=r"\[0,1\]"):
        cvr.expected_per_share()


def test_implied_ev_adds_net_debt_to_total_consideration():
    t = terms()
    assert t.implied_enterprise_value() == pytest.approx(5_000.0 + 200.0 + 500.0)


def test_ev_reconciliation_reports_the_gap_rather_than_adopting_the_stated_figure():
    t = terms()  # derived 5,700 vs stated 5,700
    assert "ties" in t.ev_reconciliation()


def test_ev_reconciliation_flags_divergence():
    from dataclasses import replace
    t = replace(terms(), stated_enterprise_value=sourced("stated", 4_000.0, CITE))
    assert "DIVERGES" in t.ev_reconciliation()


def test_premium_uses_upfront_only_not_the_contingent_maximum():
    """A premium quoted inclusive of a CVR is a maximum, not a premium."""
    assert terms().premium_to_unaffected() == pytest.approx(100.0 / 80.0 - 1.0)


def test_terms_register_their_assumptions():
    reg = AssumptionRegister()
    terms().register(reg)
    assert "cvr_weight" in {i.name for i in reg.assumptions}
