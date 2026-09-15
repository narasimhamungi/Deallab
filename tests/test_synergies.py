import pytest
from fixtures import CITE, synergy_case

from deallab.provenance import assumed, sourced
from deallab.synergies import CostToAchieve, SynergyCase, SynergyItem, SynergyType


def test_phase_in_means_year_one_is_not_the_run_rate():
    """Dropping a year-four run rate into year one is the standard way merger models
    manufacture day-one accretion."""
    c = synergy_case()
    assert c.year(1).cost == pytest.approx(200.0 * 0.25)
    assert c.year(4).cost == pytest.approx(200.0)


def test_phase_in_holds_at_its_final_value_beyond_the_schedule():
    assert synergy_case().year(9).cost == pytest.approx(200.0)


def test_revenue_synergies_are_margined_not_booked_as_pure_profit():
    c = synergy_case()
    assert c.year(5).revenue == pytest.approx(300.0 * 1.0 * 0.40)


def test_revenue_synergy_without_a_margin_is_rejected_at_construction():
    with pytest.raises(ValueError, match="contribution margin"):
        SynergyItem("Cross-sell", SynergyType.REVENUE,
                    sourced("r", 100.0, CITE), phase_in=(1.0,))


def test_dis_synergies_reduce_the_total():
    """J&J ran Abiomed standalone -- a deliberate decision to forgo integration
    synergy. A model needs to be able to express a negative."""
    c = SynergyCase((
        SynergyItem("Cost", SynergyType.COST, sourced("c", 100.0, CITE), (1.0,)),
        SynergyItem("Customer attrition", SynergyType.DIS_SYNERGY,
                    sourced("d", 40.0, CITE), (1.0,)),
    ))
    assert c.year(1).gross_pretax == pytest.approx(60.0)
    assert c.run_rate_total() == pytest.approx(60.0)


def test_negative_phase_in_is_rejected_because_the_sign_belongs_to_the_category():
    with pytest.raises(ValueError, match="DIS_SYNERGY"):
        SynergyItem("x", SynergyType.COST, sourced("c", 10.0, CITE), (-0.5,))


def test_cost_to_achieve_reduces_net_but_not_gross():
    y = synergy_case().year(1)
    assert y.cost_to_achieve == 150.0
    assert y.net_pretax == pytest.approx(y.gross_pretax - 150.0)


def test_npv_discounts_after_tax_benefit_net_of_cost_to_achieve():
    c = SynergyCase(
        (SynergyItem("Cost", SynergyType.COST, sourced("c", 100.0, CITE), (1.0,)),),
        CostToAchieve((50.0,)))
    npv = c.npv(sourced("r", 0.10, CITE), sourced("t", 0.20, CITE), years=1)
    assert npv.pv_benefit == pytest.approx(100.0 * 0.8 / 1.1)
    assert npv.pv_cost_to_achieve == pytest.approx(50.0 * 0.8 / 1.1)
    assert npv.net_npv == pytest.approx((100.0 - 50.0) * 0.8 / 1.1)


def test_terminal_growth_at_or_above_the_discount_rate_is_refused():
    c = synergy_case()
    with pytest.raises(ValueError, match="does not converge"):
        c.npv(sourced("r", 0.08, CITE), sourced("t", 0.21, CITE), years=5,
              terminal_growth=assumed("g", 0.08, CITE))


def test_excluding_revenue_synergies_lowers_the_npv():
    """The sensitivity that matters most: revenue synergies are the ones that fail."""
    c = synergy_case()
    r, t = sourced("r", 0.08, CITE), sourced("t", 0.21, CITE)
    assert c.npv_excluding_revenue_synergies(r, t).net_npv < c.npv(r, t).net_npv
