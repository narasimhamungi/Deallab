import pytest

from deallab.calendarize import (
    CalendarizationError,
    FiscalCalendar,
    calendarize,
    stub_period,
)

ABIOMED = FiscalCalendar("Abiomed", fy_end_month=3)
JNJ = FiscalCalendar("Johnson & Johnson", fy_end_month=12)


def test_march_fye_target_overlaps_a_december_buyer_by_three_months():
    assert ABIOMED.months_of_overlap(JNJ) == 3


def test_aligned_calendars_overlap_a_full_year():
    assert JNJ.months_of_overlap(JNJ) == 12


def test_calendarize_blends_adjacent_target_years_by_month_weight():
    target = {2022: {"revenue": 1_000.0}, 2023: {"revenue": 1_400.0}}
    out = calendarize(target, ABIOMED, JNJ, buyer_fiscal_year=2022)
    # 3/12 of FY2022 + 9/12 of FY2023
    assert out.values["revenue"] == pytest.approx(0.25 * 1_000.0 + 0.75 * 1_400.0)
    assert "25%" in out.method and "75%" in out.method


def test_calendarization_error_is_material_for_a_fast_growing_target():
    """The whole reason this module exists: ignoring a 9-month offset on a 40%-growth
    target misstates contributed revenue by a sixth."""
    target = {2022: {"revenue": 1_000.0}, 2023: {"revenue": 1_400.0}}
    naive = target[2022]["revenue"]
    correct = calendarize(target, ABIOMED, JNJ, 2022).values["revenue"]
    assert (correct - naive) / naive > 0.25


def test_aligned_calendars_pass_through_unadjusted():
    target = {2022: {"revenue": 900.0}}
    out = calendarize(target, JNJ, JNJ, 2022)
    assert out.values["revenue"] == 900.0
    assert "no adjustment" in out.method


def test_balance_sheet_items_are_refused_not_interpolated():
    target = {2022: {"total_assets": 1.0}, 2023: {"total_assets": 2.0}}
    with pytest.raises(CalendarizationError, match="point-in-time"):
        calendarize(target, ABIOMED, JNJ, 2022, items=("total_assets",))


def test_missing_adjacent_year_refuses_rather_than_extrapolating():
    with pytest.raises(CalendarizationError, match="fabricate"):
        calendarize({2022: {"revenue": 1.0}}, ABIOMED, JNJ, 2022)


def test_december_close_into_a_december_year_end_is_a_days_long_stub():
    """J&J closed Abiomed on 22 December 2022 and disclosed no material 2022 impact.
    A model contributing a full year to FY2022 would contradict a disclosed fact."""
    stub = stub_period("2022-12-22", buyer_fy_end_month=12, buyer_fy_end_day=31)
    assert stub.days == 9
    assert stub.fraction_of_year < 0.03


def test_mid_year_close_produces_a_partial_year():
    stub = stub_period("2024-06-30", buyer_fy_end_month=12, buyer_fy_end_day=31)
    assert 0.4 < stub.fraction_of_year < 0.6
