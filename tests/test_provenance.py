import pytest

from deallab.provenance import (
    AssumptionRegister,
    Basis,
    Input,
    MissingInputError,
    assumed,
    demonstrated,
    sourced,
    unsourced,
)


def test_sourced_input_requires_a_citation():
    with pytest.raises(ValueError, match="no citation"):
        Input("wacc", 0.08, Basis.SOURCED, "")


def test_assumed_input_requires_reasoning_not_just_a_value():
    """An assumption without a stated reason is a guess wearing a label."""
    with pytest.raises(ValueError, match="no citation"):
        assumed("synergy_run_rate", 250.0, "   ")


def test_demonstrated_input_needs_no_citation():
    d = demonstrated("shares", 45.1)
    assert d.basis is Basis.DEMONSTRATED
    assert d.required() == 45.1


def test_missing_input_raises_with_its_own_instructions_rather_than_defaulting():
    i = unsourced("target_net_debt_mm", "Take it from the Q3 10-Q balance sheet.")
    assert i.is_missing
    with pytest.raises(MissingInputError, match="Q3 10-Q"):
        i.required()


def test_unsourced_is_not_an_assumption():
    """Evidence that exists but hasn't been collected must not hide in the assumption
    register -- otherwise a researchable fact stays 'assumed' forever."""
    reg = AssumptionRegister()
    reg.record(unsourced("net_debt", "go read the 10-Q"))
    assert reg.missing and not reg.assumptions


def test_register_separates_assumptions_from_missing_and_ignores_sourced():
    reg = AssumptionRegister()
    reg.record(
        sourced("price", 380.0, "8-K"),
        assumed("cvr_weight", 0.4, "no disclosed FV located"),
        unsourced("book_equity", "10-Q"),
    )
    assert [i.name for i in reg.assumptions] == ["cvr_weight"]
    assert [i.name for i in reg.missing] == ["book_equity"]
    assert "price" not in reg.report()


def test_register_deduplicates_by_name():
    reg = AssumptionRegister()
    a = assumed("tax_rate", 0.21, "statutory")
    reg.record(a)
    reg.record(a)
    assert len(reg.entries) == 1


def test_report_says_so_when_nothing_is_assumed_or_missing():
    assert "Demonstrated or Sourced" in AssumptionRegister().report()
