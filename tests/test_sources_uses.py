from dataclasses import replace

import pytest
from fixtures import CITE, plan, terms

from deallab import sources_uses
from deallab.provenance import sourced


def test_a_correctly_sized_funding_plan_balances():
    t = terms()
    # uses: 5,000 upfront + 500 repay debt + 50 advisory = 5,550. The CVR is NOT
    # funded at close -- it is an ASC 805 liability, not day-one cash.
    p = plan(cash=1_550.0, debt=4_000.0)
    su = sources_uses.build(t, p)
    assert su.balanced, su.note
    assert su.total_sources == pytest.approx(su.total_uses)


def test_an_unbalanced_plan_is_reported_not_silently_plugged():
    su = sources_uses.build(terms(), plan(cash=100.0, debt=100.0))
    assert not su.balanced
    assert su.gap < 0
    assert "shortfall" in su.note


def test_target_net_cash_becomes_a_source_not_a_use():
    """Paying an enterprise value for a net-cash target means the cash comes across."""
    t = replace(terms(), target_net_debt=sourced("nd", -300.0, CITE))
    su = sources_uses.build(t, plan(cash=1_000.0, debt=4_000.0))
    assert "Target cash acquired" in su.sources
    assert su.sources["Target cash acquired"] == 300.0
    assert not any("Repay target debt" in k for k in su.uses)


def test_cvr_is_not_funded_at_close_by_default():
    """A CVR is recognised as a liability at acquisition date and consumes cash only
    when milestones are met. Showing it as a day-one use overstates the funding
    requirement -- and therefore the interest drag -- by its full fair value."""
    su = sources_uses.build(terms(), plan(cash=1_550.0, debt=4_000.0))
    assert not any("Contingent" in k for k in su.uses)
    assert "deliberately EXCLUDED from uses" in su.note


def test_cvr_can_be_prefunded_when_the_structure_actually_escrows_it():
    su = sources_uses.build(terms(), plan(cash=1_750.0, debt=4_000.0),
                            fund_contingent_at_close=True)
    assert su.uses["Contingent consideration (CVR, prefunded at close)"] == pytest.approx(200.0)
    assert "NOT the default treatment" in su.note


def test_cvr_still_enters_goodwill_even_though_it_is_not_a_cash_use():
    """The distinction that matters: out of sources & uses, into the allocation."""
    t = terms()
    assert t.total_equity_purchase_price() > t.upfront_equity_purchase_price()


def test_not_refinancing_target_debt_removes_it_from_uses():
    su = sources_uses.build(terms(), plan(), refinance_target_debt=False)
    assert not any("Repay target debt" in k for k in su.uses)


def test_expensed_fees_are_a_use_of_cash_even_though_they_never_touch_goodwill():
    su = sources_uses.build(terms(), plan())
    assert su.uses["Advisory/legal fees (expensed)"] == 50.0


def test_funding_plan_sized_off_upfront_only_balances_with_cvr_present():
    """Regression test for a real bug: an earlier orchestration script sized its
    funding plan off total_equity_purchase_price() (upfront + CVR), then handed that
    oversized amount to a sources_uses.build() that correctly excludes the CVR from
    day-one uses (see test_cvr_is_not_funded_at_close_by_default above). The mismatch
    was exactly the CVR's fair value, and the balance check caught it on the first
    real-data run. The correct pattern -- funding plan sized off upfront-only -- must
    balance; sizing off the CVR-inclusive total must NOT."""
    t = terms()
    # this fixture's target has $500mm of net DEBT (not net cash), so it is repaid
    # as a use too -- matching the terms()/plan() pair test_a_correctly_sized_...
    # already establishes as balanced.
    correct_funding = t.upfront_equity_purchase_price() + 500.0 + 50.0
    su_correct = sources_uses.build(t, plan(cash=correct_funding - 4_000.0, debt=4_000.0))
    assert su_correct.balanced

    wrong_funding = t.total_equity_purchase_price() + 500.0 + 50.0  # bug: includes CVR
    su_wrong = sources_uses.build(t, plan(cash=wrong_funding - 4_000.0, debt=4_000.0))
    assert not su_wrong.balanced
    assert su_wrong.gap == pytest.approx(t.contingent_consideration_fair_value(), abs=1.0)
