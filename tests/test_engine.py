import pytest
from fixtures import (
    CITE,
    buyer_years,
    intangibles,
    plan,
    synergy_case,
    target_years,
    terms,
)

from deallab import engine
from deallab.provenance import sourced


def _model(**kw):
    defaults = {
        "terms": terms(), "plan": plan(cash=1_550.0, debt=4_000.0),
        "synergies": synergy_case(), "intangibles": intangibles(),
        "buyer_years": buyer_years(), "target_years": target_years(),
        "buyer_shares": sourced("shares_mm", 1_000.0, CITE),
        "buyer_tax_rate": sourced("buyer_tax", 0.21, CITE),
        "target_tax_rate": sourced("target_tax", 0.21, CITE),
        "target_book_equity": sourced("book_mm", 1_000.0, CITE),
    }
    defaults.update(kw)
    return engine.DealModel(**defaults)


def test_end_to_end_run_produces_every_stage():
    r = engine.run(_model())
    assert r.sources_uses.balanced
    assert r.allocation.goodwill > 0
    assert len(r.pro_forma) == len(r.accretion) == 5
    assert r.breakeven.required_pretax is not None


def test_mismatched_forecast_lengths_are_refused_not_silently_truncated():
    with pytest.raises(ValueError, match="silently dropped"):
        _model(buyer_years=buyer_years(5), target_years=target_years(3))


def test_the_assumption_register_is_populated_before_any_result_is_read():
    r = engine.run(_model())
    names = {i.name for i in r.register.assumptions}
    assert {"cvr_weight", "foregone_yield", "rev_syn_margin"} <= names
    assert "ASSUMPTIONS" in r.register.report()


def test_transaction_costs_hit_year_one_only():
    r = engine.run(_model())
    y1 = {s.label for s in r.pro_forma[0].steps}
    y2 = {s.label for s in r.pro_forma[1].steps}
    assert any("Transaction costs" in s for s in y1)
    assert not any("Transaction costs" in s for s in y2)


def test_a_stub_year_reduces_year_one_contribution_and_accretion():
    full = engine.run(_model())
    stub = engine.run(_model(stub_fraction_year_one=0.1))
    assert stub.accretion[0].adjusted_pct < full.accretion[0].adjusted_pct
    assert stub.accretion[1].adjusted_pct == pytest.approx(full.accretion[1].adjusted_pct)


def test_accretion_improves_over_time_as_synergies_phase_in():
    r = engine.run(_model())
    assert r.accretion[3].adjusted_pct > r.accretion[0].adjusted_pct


def test_gaap_trails_adjusted_in_every_year_while_amortisation_runs():
    r = engine.run(_model())
    for a in r.accretion[:5]:
        assert a.gaap_pct < a.adjusted_pct


def test_equity_funding_dilutes_where_debt_funding_does_not():
    """The question a merger model must be able to answer: would this still be
    accretive if it were equity funded?"""
    debt = engine.run(_model(plan=plan(cash=1_550.0, debt=4_000.0)))
    eq = engine.run(_model(plan=plan(cash=1_550.0, debt=0.0, equity_mm=4_000.0)))
    assert eq.accretion[0].adjusted_pct < debt.accretion[0].adjusted_pct
    assert "Share count dilution from equity issued" in eq.accretion[0].attribution


def test_verdict_assembles_both_lenses_from_a_completed_run():
    r = engine.run(_model())
    npv = synergy_case().npv(sourced("r", 0.08, CITE), sourced("t", 0.21, CITE))
    ex = synergy_case().npv_excluding_revenue_synergies(
        sourced("r", 0.08, CITE), sourced("t", 0.21, CITE))
    v = engine.build_verdict(r, standalone_value=4_000.0,
                             standalone_basis="DCF mid, test",
                             synergy_npv=npv.net_npv,
                             synergy_npv_ex_revenue=ex.net_npv, wacc=0.08)
    assert v.accounting.year_one.year_index == 1
    assert v.economic.premium_paid == pytest.approx(
        r.allocation.consideration_transferred - 4_000.0)
    assert v.disagreement


def test_formatted_output_leads_with_assumptions_not_with_the_answer():
    out = engine.run(_model()).format()
    assert out.index("ASSUMPTIONS") < out.index("ACCRETION / DILUTION")
