import pytest
from fixtures import CITE, intangibles

from deallab.provenance import sourced
from deallab.purchase_accounting import allocate, step_up_charges


def _allocate(consideration=6_000.0, book=1_000.0, tax=0.21, deductible=False,
              inventory=None, ppe=None):
    return allocate(
        consideration_transferred=consideration,
        target_book_equity=sourced("book", book, CITE),
        intangibles=intangibles(),
        buyer_tax_rate=sourced("tax", tax, CITE),
        inventory_step_up=sourced("inv", inventory, CITE) if inventory else None,
        ppe_step_up=sourced("ppe", ppe, CITE) if ppe else None,
        step_up_tax_deductible=deductible,
    )


def test_goodwill_is_the_residual_after_step_up_and_dtl():
    a = _allocate()
    # 6,000 - 1,000 book - 3,000 intangibles + 630 DTL = 2,630
    assert a.deferred_tax_liability == pytest.approx(3_000.0 * 0.21)
    assert a.goodwill == pytest.approx(6_000.0 - 1_000.0 - 3_000.0 + 630.0)


def test_omitting_the_dtl_would_understate_goodwill_by_a_quarter_of_the_step_up():
    """Stock deal: step-up is not deductible, a DTL arises, goodwill rises."""
    with_dtl = _allocate(deductible=False).goodwill
    without = _allocate(deductible=True).goodwill
    assert with_dtl - without == pytest.approx(3_000.0 * 0.21)


def test_inventory_and_ppe_step_ups_increase_the_dtl_and_reduce_goodwill_net():
    a = _allocate(inventory=200.0, ppe=300.0)
    total_step_up = 3_000.0 + 200.0 + 300.0
    assert a.deferred_tax_liability == pytest.approx(total_step_up * 0.21)
    assert a.goodwill == pytest.approx(
        6_000.0 - 1_000.0 - total_step_up + total_step_up * 0.21)


def test_negative_goodwill_is_flagged_as_an_input_error_not_reported_silently():
    a = _allocate(consideration=500.0)
    assert a.goodwill < 0
    assert any("bargain purchase" in n for n in a.notes)


def test_goodwill_heavy_allocation_is_flagged():
    a = allocate(consideration_transferred=10_000.0,
                 target_book_equity=sourced("book", 100.0, CITE),
                 intangibles=(), buyer_tax_rate=sourced("tax", 0.21, CITE))
    assert any("Goodwill is" in n for n in a.notes)
    assert any("no identifiable intangibles" in n.lower() for n in a.notes)


def test_amortisation_is_straight_line_and_stops_at_end_of_useful_life():
    a = _allocate()
    ints = intangibles()
    # dev tech 2,000/10 = 200; customer rel 1,000/5 = 200 -> 400 for years 1-5
    assert step_up_charges(1, ints, a).intangible_amortisation == pytest.approx(400.0)
    assert step_up_charges(5, ints, a).intangible_amortisation == pytest.approx(400.0)
    # customer relationships expire after year 5
    assert step_up_charges(6, ints, a).intangible_amortisation == pytest.approx(200.0)
    assert step_up_charges(11, ints, a).intangible_amortisation == pytest.approx(0.0)


def test_inventory_step_up_hits_year_one_only_and_is_not_recurring():
    a = _allocate(inventory=200.0)
    c1 = step_up_charges(1, intangibles(), a)
    c2 = step_up_charges(2, intangibles(), a)
    assert c1.inventory_step_up_unwind == 200.0
    assert c2.inventory_step_up_unwind == 0.0
    assert c1.recurring == pytest.approx(c1.total - 200.0)


def test_incremental_depreciation_runs_over_the_remaining_ppe_life():
    a = _allocate(ppe=300.0)
    c = step_up_charges(1, intangibles(), a,
                        ppe_remaining_life_years=sourced("life", 10.0, CITE))
    assert c.incremental_depreciation == pytest.approx(30.0)


def test_disclosed_dtl_overrides_the_statutory_rate_calculation():
    """Sourcing a fact and then using a self-computed approximation instead is the
    specific failure this parameter exists to prevent."""
    computed = _allocate().deferred_tax_liability
    a = allocate(
        consideration_transferred=6_000.0,
        target_book_equity=sourced("book", 1_000.0, CITE),
        intangibles=intangibles(),
        buyer_tax_rate=sourced("tax", 0.21, CITE),
        sourced_deferred_tax_liability=sourced("disclosed_dtl", 900.0, CITE))
    assert a.deferred_tax_liability == 900.0
    assert a.deferred_tax_liability != computed
    assert any("taken from disclosure, not computed" in n for n in a.notes)


def test_dtl_override_note_quantifies_the_gap_it_closes():
    """The difference flows straight into goodwill, so its size belongs in the output."""
    a = allocate(
        consideration_transferred=6_000.0,
        target_book_equity=sourced("book", 1_000.0, CITE),
        intangibles=intangibles(),
        buyer_tax_rate=sourced("tax", 0.21, CITE),
        sourced_deferred_tax_liability=sourced("disclosed_dtl", 900.0, CITE))
    note = next(n for n in a.notes if "taken from disclosure" in n)
    assert "630" in note and "900" in note  # computed vs disclosed, both stated


def test_a_missing_sourced_dtl_falls_back_to_computation_rather_than_zero():
    from deallab.provenance import unsourced
    a = allocate(
        consideration_transferred=6_000.0,
        target_book_equity=sourced("book", 1_000.0, CITE),
        intangibles=intangibles(),
        buyer_tax_rate=sourced("tax", 0.21, CITE),
        sourced_deferred_tax_liability=unsourced("dtl", "go read the 10-K"))
    assert a.deferred_tax_liability == pytest.approx(3_000.0 * 0.21)


def _iprd():
    from deallab.purchase_accounting import IntangibleClass
    return IntangibleClass("IPR&D", sourced("iprd", 1_000.0, CITE),
                           useful_life_years=None)


def test_indefinite_lived_intangibles_are_never_amortised():
    """ASC 350-30: IPR&D acquired in a business combination is capitalised as
    indefinite-lived and tested for impairment, not amortised."""
    i = _iprd()
    assert i.indefinite_lived
    assert i.annual_amortisation() == 0.0
    assert i.amortisation(1) == 0.0
    assert i.amortisation(50) == 0.0


def test_indefinite_lived_intangibles_still_reduce_goodwill():
    """They are identifiable assets -- excluding them would overstate goodwill by
    their full fair value, which on J&J/Abiomed is 6% of the deal."""
    without = allocate(
        consideration_transferred=6_000.0,
        target_book_equity=sourced("book", 1_000.0, CITE),
        intangibles=intangibles(), buyer_tax_rate=sourced("tax", 0.21, CITE))
    with_iprd = allocate(
        consideration_transferred=6_000.0,
        target_book_equity=sourced("book", 1_000.0, CITE),
        intangibles=intangibles() + (_iprd(),),
        buyer_tax_rate=sourced("tax", 0.21, CITE))
    # goodwill falls by the IPR&D value, net of the extra DTL it attracts
    assert with_iprd.goodwill < without.goodwill
    assert with_iprd.identifiable_intangibles == without.identifiable_intangibles + 1_000.0


def test_indefinite_lived_assets_sit_inside_the_dtl_step_up():
    a = allocate(
        consideration_transferred=6_000.0,
        target_book_equity=sourced("book", 1_000.0, CITE),
        intangibles=intangibles() + (_iprd(),),
        buyer_tax_rate=sourced("tax", 0.21, CITE))
    assert a.deferred_tax_liability == pytest.approx(4_000.0 * 0.21)


def test_indefinite_lived_holding_is_flagged_in_the_notes():
    a = allocate(
        consideration_transferred=6_000.0,
        target_book_equity=sourced("book", 1_000.0, CITE),
        intangibles=intangibles() + (_iprd(),),
        buyer_tax_rate=sourced("tax", 0.21, CITE))
    assert any("indefinite-lived" in n and "NO amortisation" in n for n in a.notes)


def test_a_mixed_portfolio_amortises_only_the_finite_lived_classes():
    from deallab.purchase_accounting import step_up_charges
    mixed = intangibles() + (_iprd(),)
    a = allocate(
        consideration_transferred=6_000.0,
        target_book_equity=sourced("book", 1_000.0, CITE),
        intangibles=mixed, buyer_tax_rate=sourced("tax", 0.21, CITE))
    # unchanged from the finite-only case: 2,000/10 + 1,000/5 = 400
    assert step_up_charges(1, mixed, a).intangible_amortisation == pytest.approx(400.0)
