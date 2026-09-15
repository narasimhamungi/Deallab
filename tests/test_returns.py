import pytest
from fixtures import CITE

from deallab.provenance import assumed, sourced
from deallab.returns import IRRError, irr, npv, run


def test_irr_recovers_a_known_rate():
    # -100 now, 110 in a year = 10%
    assert irr([-100.0, 110.0]) == pytest.approx(0.10, abs=1e-6)


def test_irr_zeroes_the_npv_it_solves():
    flows = [-1_000.0, 200.0, 300.0, 400.0, 500.0]
    assert npv(irr(flows), flows) == pytest.approx(0.0, abs=1e-6)


def test_irr_refuses_flows_with_no_sign_change_instead_of_returning_a_number():
    with pytest.raises(IRRError, match="sign change"):
        irr([100.0, 200.0])


def test_irr_reports_when_no_root_is_bracketed():
    with pytest.raises(IRRError, match="bracketed"):
        irr([-1.0, 0.0001], lo=0.5, hi=10.0)


def _run(exit_mult=10.0, entry_mult=10.0, hurdle=0.08):
    return run(
        entry_equity_outlay=sourced("entry", 1_000.0, CITE),
        free_cash_flows=[50.0, 60.0, 70.0, 80.0, 90.0],
        exit_ebitda=sourced("ebitda", 150.0, CITE),
        exit_multiple=assumed("mult", exit_mult, CITE),
        exit_net_debt=sourced("nd", 0.0, CITE),
        hurdle_rate=sourced("hurdle", hurdle, CITE),
        entry_multiple=entry_mult,
    )


def test_exit_equals_entry_multiple_is_flagged_as_the_conservative_convention():
    r = _run()
    assert any("conservative convention" in w for w in r.warnings)


def test_multiple_expansion_is_flagged_as_an_assumption_about_the_market():
    r = _run(exit_mult=14.0)
    assert any("multiple expansion" in w for w in r.warnings)


def test_hurdle_comparison_is_reported_both_ways():
    assert _run(hurdle=0.01).clears_hurdle is True
    assert _run(hurdle=0.99).clears_hurdle is False


def test_moic_below_one_is_flagged_before_the_irr_is_read():
    r = run(entry_equity_outlay=sourced("entry", 1_000.0, CITE),
            free_cash_flows=[10.0, 10.0],
            exit_ebitda=sourced("e", 10.0, CITE),
            exit_multiple=assumed("m", 2.0, CITE),
            exit_net_debt=sourced("nd", 0.0, CITE))
    assert r.moic < 1.0
    assert any("MOIC below 1.0x" in w for w in r.warnings)


def test_deriving_entry_multiple_from_exit_year_ebitda_erases_growth_value():
    """Regression test for a real bug: an earlier orchestration script computed
    entry_multiple = EV / EXIT-year EBITDA, then applied that same multiple at exit.
    That is circular -- exit_equity = exit_ebitda * (EV / exit_ebitda) = EV exactly,
    algebraically, no matter how much the business grows. Caught on a real-data run
    when a business modelled to grow double digits produced MOIC ~1.0x and IRR ~0%,
    which does not happen without a construction error."""
    ev = 17_916.0
    year1_ebitda, year5_ebitda = 250.0, 500.0  # doubles over the horizon
    fcf = [30.0, 40.0, 50.0, 60.0, 70.0]

    # THE BUG: multiple derived from the same EBITDA figure it is later applied to.
    circular_multiple = ev / year5_ebitda
    circular = run(
        entry_equity_outlay=sourced("entry", ev, CITE),
        free_cash_flows=fcf,
        exit_ebitda=sourced("exit_ebitda", year5_ebitda, CITE),
        exit_multiple=assumed("mult", circular_multiple, CITE),
        exit_net_debt=sourced("nd", 0.0, CITE))
    # exit_equity collapses to ~EV regardless of the FCF or the growth -- the tell
    assert circular.exit_equity == pytest.approx(ev, rel=0.01)
    assert circular.moic < 1.2  # cumulative FCF is the only value creation left

    # THE FIX: multiple derived from an entry-proximate EBITDA figure instead.
    correct_multiple = ev / year1_ebitda
    correct = run(
        entry_equity_outlay=sourced("entry", ev, CITE),
        free_cash_flows=fcf,
        exit_ebitda=sourced("exit_ebitda", year5_ebitda, CITE),
        exit_multiple=assumed("mult", correct_multiple, CITE),
        exit_net_debt=sourced("nd", 0.0, CITE))
    # now the doubling of EBITDA actually shows up as doubled exit equity value
    assert correct.exit_equity == pytest.approx(ev * (year5_ebitda / year1_ebitda), rel=0.01)
    assert correct.moic > circular.moic  # growth is now credited, not erased
