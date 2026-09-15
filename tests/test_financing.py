import pytest
from fixtures import CITE, plan

from deallab.financing import DebtTranche, FinancingPlan
from deallab.provenance import assumed, sourced


def test_foregone_interest_income_is_booked_not_ignored():
    """Cash spent on an acquisition stops earning. Omitting this is a silent subsidy."""
    p = plan(cash=1_000.0)
    assert p.foregone_interest_income() == pytest.approx(1_000.0 * 0.04)


def test_pretax_financing_cost_includes_both_interest_and_foregone_income():
    p = plan(cash=1_000.0, debt=4_000.0)
    assert p.pretax_financing_cost(1) == pytest.approx(4_000.0 * 0.05 + 1_000.0 * 0.04)


def test_bullet_tranche_interest_is_flat_across_years():
    t = DebtTranche("Notes", sourced("p", 1_000.0, CITE), sourced("r", 0.05, CITE))
    assert t.interest_expense(1) == t.interest_expense(5) == pytest.approx(50.0)


def test_amortising_tranche_charges_interest_on_the_average_balance():
    t = DebtTranche("Term loan", sourced("p", 1_000.0, CITE), sourced("r", 0.10, CITE),
                    tenor_years=sourced("tenor", 5.0, CITE), amortising=True)
    # year 1: opening 1000, closing 800, average 900
    assert t.interest_expense(1) == pytest.approx(90.0)
    assert t.interest_expense(5) == pytest.approx(10.0)
    assert t.interest_expense(6) == 0.0


def test_amortising_balance_reaches_zero_and_does_not_go_negative():
    t = DebtTranche("Term loan", sourced("p", 500.0, CITE), sourced("r", 0.05, CITE),
                    tenor_years=sourced("tenor", 5.0, CITE), amortising=True)
    assert t.balance(5) == pytest.approx(0.0)
    assert t.balance(9) == 0.0


def test_advisory_fees_are_expensed_and_kept_apart_from_issuance_costs():
    """ASC 805: deal costs are expensed; debt issuance costs are capitalised. A model
    that adds banker fees to the purchase price is wrong in an interviewable way."""
    p = FinancingPlan(
        cash_on_hand_used=sourced("cash", 0.0, CITE),
        foregone_yield=assumed("y", 0.0, CITE),
        tranches=(DebtTranche("Notes", sourced("p", 1_000.0, CITE),
                              sourced("r", 0.05, CITE),
                              issuance_fee_pct=sourced("fee", 0.01, CITE)),),
        advisory_fees=sourced("adv", 40.0, CITE),
    )
    assert p.expensed_transaction_costs() == 40.0
    assert p.total_issuance_fees() == pytest.approx(10.0)


def test_equity_without_a_price_refuses_rather_than_guessing_the_share_count():
    p = FinancingPlan(
        cash_on_hand_used=sourced("cash", 0.0, CITE),
        foregone_yield=assumed("y", 0.0, CITE),
        new_equity_issued=sourced("eq", 1_000.0, CITE),
    )
    with pytest.raises(ValueError, match="share count"):
        p.new_shares_issued()


def test_new_share_count_derives_from_proceeds_and_price():
    assert plan(equity_mm=1_000.0).new_shares_issued() == pytest.approx(20.0)
