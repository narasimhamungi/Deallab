"""The real deal fixture: checks that it contains evidence, not placeholders."""
import pytest

from deallab.deals import jnj_abiomed as deal
from deallab.provenance import Basis


def test_sourced_consideration_matches_the_8k():
    assert deal.TERMS.cash_per_share.value == 380.00
    assert deal.CVR.max_per_share.value == 35.00
    assert deal.TERMS.stated_enterprise_value.value == 16_600.0
    assert "sec.gov" in deal.TERMS.cash_per_share.citation


def test_share_count_is_sourced_directly_not_only_derived():
    """Directly disclosed on the Abiomed 10-Q cover page (45,091,184 as of 28 Oct
    2022), cross-checked against the independent tender-based derivation
    (25,759,195 / 0.571 = 45.11mm) -- the two agree to within 0.05%."""
    assert deal.TARGET_SHARES_OUTSTANDING.basis is Basis.SOURCED
    assert deal.TARGET_SHARES_OUTSTANDING.value == pytest.approx(45.091184)
    tender_derived = 25_759_195 / 0.571 / 1e6
    assert deal.TARGET_SHARES_OUTSTANDING.value == pytest.approx(tender_derived, rel=0.001)
    assert "not fully diluted" in deal.TARGET_SHARES_OUTSTANDING.citation


def test_upfront_consideration_lands_near_the_stated_enterprise_value():
    """A ~45.09mm share count at $380 gives ~$17.1bn of upfront equity value against a
    stated $16.6bn EV 'including cash acquired' -- the gap is Abiomed's net cash, which
    is the check that the derived share count is roughly right."""
    upfront = deal.TERMS.upfront_equity_purchase_price()
    assert 16_500 < upfront < 17_500


def test_target_net_debt_and_book_equity_are_now_sourced():
    """Both were UNSOURCED in an earlier pass -- both are now pulled from Abiomed's
    actual 30 June 2022 10-Q, the correct 'last balance sheet before announcement'
    (the 30 Sept 2022 10-Q this file previously pointed to was filed 3 Nov 2022, two
    days AFTER the 1 Nov announcement -- not actually available at signing)."""
    assert deal.TARGET_NET_DEBT.basis is Basis.SOURCED
    assert deal.TARGET_NET_DEBT.value == pytest.approx(-1_004.197)
    assert deal.TARGET_BOOK_EQUITY.basis is Basis.SOURCED
    assert deal.TARGET_BOOK_EQUITY.value == pytest.approx(1_536.196)
    assert "no debt" in deal.TARGET_NET_DEBT.citation


def test_target_fundamentals_tie_to_each_other_exactly():
    """Pretax income less the tax provision equals net income to the dollar -- an
    internal consistency check a secondary-sourced figure could never offer."""
    pretax = 190.560
    tax = 54.055
    assert pretax - tax == pytest.approx(deal.TARGET_NET_INCOME_FY2022.value, abs=0.001)
    assert deal.TARGET_EFFECTIVE_TAX_RATE_FY2022.value == pytest.approx(tax / pretax)


def test_effective_tax_rate_is_flagged_as_elevated_not_just_reported():
    assert deal.TARGET_EFFECTIVE_TAX_RATE_FY2022.value > 0.21  # above statutory
    assert "foreign" in deal.TARGET_EFFECTIVE_TAX_RATE_FY2022.citation.lower()


def test_upfront_only_gap_to_stated_ev_is_real_and_material_not_rounding():
    """The whole point of computing this rather than adopting the stated figure: the
    gap is ~2.8% of deal value, not noise, and the fixture says so rather than
    quietly reconciling to a number it can't actually derive."""
    upfront = deal.TERMS.upfront_equity_purchase_price()
    derived_ev_ex_cvr = upfront + deal.TARGET_NET_DEBT.value
    gap = derived_ev_ex_cvr - deal.STATED_EV.value
    assert gap == pytest.approx(-469.5, abs=1.0)
    assert abs(gap) / deal.STATED_EV.value > 0.02


def test_full_ev_reconciliation_now_runs_with_the_cvr_weight_assumed():
    """This used to raise MissingInputError -- now that the CVR weight is an ASSUMED
    estimate rather than unset, the full reconciliation (upfront + CVR at FV + net
    debt, vs. stated EV) can actually run. The gap including the CVR is smaller than
    the upfront-only gap above, since the CVR fair value adds to the derived EV."""
    result = deal.TERMS.ev_reconciliation()
    assert "DIVERGES" in result or "ties" in result
    with_cvr = deal.TERMS.implied_enterprise_value()
    upfront_only = deal.TERMS.upfront_equity_purchase_price() + deal.TARGET_NET_DEBT.value
    assert with_cvr > upfront_only  # CVR fair value narrows, doesn't widen, the gap


def test_the_cvr_probability_weight_is_now_an_assumed_cited_estimate_not_blocking():
    """Upgraded this pass from a blind unset value to a reasoned assumption -- still
    ASSUMED (not SOURCED), and the citation says explicitly why it is circumstantial."""
    assert deal.CVR.probability_weight.basis is Basis.ASSUMED
    assert not deal.CVR.probability_weight.is_missing
    assert deal.CVR.probability_weight.value == pytest.approx(0.495, abs=0.001)
    assert "CIRCUMSTANTIAL, NOT CONFIRMED" in deal.CVR.probability_weight.citation
    # and it now actually unblocks the calculation it used to raise on:
    fv = deal.TERMS.contingent_consideration_fair_value()
    assert fv > 0.0


def test_deferred_tax_liability_is_sourced_directly_and_unambiguously():
    """Unlike the CVR estimate, this one has explicit textual attribution -- 'due to
    the acquisition of Abiomed' -- and the test distinguishes the two confidence
    levels rather than treating every 'now-known' figure as equally solid."""
    assert deal.DEFERRED_TAX_LIABILITY_ABIOMED.value == 1_800.0
    assert "due to the acquisition of Abiomed" in deal.DEFERRED_TAX_LIABILITY_ABIOMED.citation


def test_total_liabilities_estimate_is_demonstrated_not_sourced_since_its_a_sum():
    """It's built from two sourced figures, not quoted as a single disclosed line --
    tagged accordingly rather than dressed up as a primary citation."""
    assert deal.TOTAL_LIABILITIES_ASSUMED_ESTIMATE.basis is Basis.DEMONSTRATED
    assert deal.TOTAL_LIABILITIES_ASSUMED_ESTIMATE.value == pytest.approx(1_956.757, abs=0.01)
    assert "NOT a single disclosed line" in deal.TOTAL_LIABILITIES_ASSUMED_ESTIMATE.citation


def test_the_cvr_is_material_enough_that_ignoring_it_would_misstate_the_price():
    assert deal.CVR.max_per_share.value / deal.TERMS.cash_per_share.value > 0.09


def test_uncollected_inputs_are_listed_with_the_filing_that_contains_them():
    """Down to 1. financing_mix left MISSING not because it was found but because it
    was never disclosed -- handled as a spanned sensitivity instead of a guess. The
    buyer forecast left because it is now produced by the Trellis pipeline."""
    assert len(deal.MISSING) == 1
    for i in deal.MISSING:
        assert i.is_missing
        assert "NOT YET COLLECTED" in i.citation
        assert any(w in i.citation for w in ("10-K", "10-Q", "Trellis"))


def test_ppa_headline_figures_are_sourced_from_jnjs_own_10k():
    assert deal.INTANGIBLE_AMORTIZABLE_FV.value == 6_600.0
    assert deal.IPRD_FV.value == 1_100.0
    assert deal.ADVISORY_FEES_PRETAX.value == 300.0
    assert "14 years" in deal.INTANGIBLE_AMORTIZABLE_FV.citation
    assert "52%-70%" in deal.IPRD_FV.citation


def test_actual_ppa_itemised_categories_sum_close_to_but_not_exactly_total_assets():
    """The four itemised categories don't sum to the stated total -- the gap is other
    identifiable assets not broken out. Left visible rather than forced to balance."""
    itemised = (deal.ACTUAL_PPA["goodwill_mm"] + deal.ACTUAL_PPA["amortizable_intangibles_mm"]
                + deal.ACTUAL_PPA["iprd_mm"]
                + deal.ACTUAL_PPA["marketable_securities_acquired_mm"])
    total = deal.ACTUAL_PPA["total_assets_acquired_net_of_cash_mm"]
    assert itemised < total
    assert 0 < (total - itemised) < 1_000.0


def test_cvr_aggregate_undiscounted_max_is_not_confused_with_acquisition_date_fair_value():
    """1.6bn is the maximum-if-everything-hits figure, not what J&J actually booked --
    the fixture keeps these conceptually and nominally separate."""
    assert deal.ACTUAL_PPA["cvr_aggregate_undiscounted_max_mm"] == 1_600.0
    assert "distinct from the $1.6bn undiscounted maximum" in deal.ACTUAL_PPA_SOURCE
    # the ASSUMED weight has a value now, but it is still not the same thing as a
    # confirmed, disclosed acquisition-date fair value -- that stays in MISSING
    assert deal.CVR.probability_weight.value is not None
    assert any(i.name == "cvr_acquisition_date_fair_value" for i in deal.MISSING)


def test_measurement_period_adjustment_discrepancy_across_filings_is_explained_not_hidden():
    assert "0.1" in deal.PPA_MEASUREMENT_PERIOD_ADJUSTMENT
    assert "0.2" in deal.PPA_MEASUREMENT_PERIOD_ADJUSTMENT
    assert "expected to differ" in deal.PPA_MEASUREMENT_PERIOD_ADJUSTMENT


def test_evs_own_restatement_across_filings_reinforces_the_rounded_pr_number_reading():
    assert "16.6" in deal.EV_RESTATEMENT_NOTE and "16.5" in deal.EV_RESTATEMENT_NOTE


def test_upfront_net_of_cash_figure_is_kept_separate_not_reconciled_into_terms():
    """J&J's own $17.1bn 'net of cash acquired' figure is NOT the same computation as
    this file's derived gross upfront consideration, and the fixture says so rather
    than quietly treating the near-equal values as confirmation of each other."""
    assert deal.UPFRONT_NET_OF_CASH_ACQUIRED.value == 17_100.0
    gross = deal.TERMS.upfront_equity_purchase_price()
    assert gross != deal.UPFRONT_NET_OF_CASH_ACQUIRED.value
    assert "coincidence of rounding" in deal.UPFRONT_NET_OF_CASH_ACQUIRED.citation


def test_no_placeholder_numbers_exist_in_the_fixture():
    """Every value is either sourced, demonstrated, cited-assumed, or absent-with-
    instructions. Nothing is invented without a stated reason."""
    for i in (deal.CASH_PER_SHARE, deal.STATED_EV, deal.CVR.max_per_share,
              deal.TARGET_SHARES_OUTSTANDING, deal.TARGET_REVENUE_FY2022,
              deal.TARGET_NET_DEBT, deal.TARGET_BOOK_EQUITY,
              deal.TARGET_OPERATING_INCOME_FY2022, deal.TARGET_NET_INCOME_FY2022,
              deal.TARGET_EFFECTIVE_TAX_RATE_FY2022, deal.DEFERRED_TAX_LIABILITY_ABIOMED,
              deal.TOTAL_LIABILITIES_ASSUMED_ESTIMATE, deal.CVR.probability_weight):
        assert i.value is not None and i.citation.strip()


def test_secondary_sourced_figures_are_flagged_for_verification():
    """Only the unaffected share price remains secondary -- revenue was upgraded to a
    primary 10-K citation this pass."""
    assert "SECONDARY SOURCE" in deal.TARGET_SHARE_PRICE_UNAFFECTED.citation
    assert "SECONDARY SOURCE" not in deal.TARGET_REVENUE_FY2022.citation


def test_revenue_upgrade_agrees_with_the_superseded_secondary_figure():
    """The primary 10-K figure and the old secondary-sourced estimate agree to within
    $0.25mm -- a useful cross-check that the secondary source had been reliable."""
    assert deal.TARGET_REVENUE_FY2022.value == pytest.approx(1_032.0, abs=0.3)


def test_guidance_captures_the_answer_key_including_the_standalone_structure():
    assert "lightly dilutive to neutral" in deal.GUIDANCE["year_one_adjusted_eps"]
    assert deal.GUIDANCE_2024_ACCRETION_USD == 0.05
    assert "standalone" in deal.GUIDANCE["integration"]
    assert "should NOT be assumed" in deal.GUIDANCE["integration"]


def test_premium_to_unaffected_uses_upfront_cash_only():
    p = deal.TERMS.premium_to_unaffected()
    assert p == pytest.approx(380.0 / 252.0 - 1.0)
    assert 0.45 < p < 0.55


def test_buyer_tax_rate_override_is_assumed_not_sourced_and_cites_multiple_disclosures():
    """A judgment call (16%, the midpoint of a disclosed range) is a real choice, not
    a single quoted figure -- ASSUMED is the correct tag, and the citation says why."""
    assert deal.BUYER_TAX_RATE_OVERRIDE.basis is Basis.ASSUMED
    assert deal.BUYER_TAX_RATE_OVERRIDE.value == 0.16
    assert "16.5%" in deal.BUYER_TAX_RATE_OVERRIDE.citation
    assert "not SOURCED" in deal.BUYER_TAX_RATE_OVERRIDE.citation


def test_buyer_tax_rate_override_explains_why_trellis_overrides_param_cant_be_used():
    """A real, checked limitation of the upstream tool, stated rather than routed
    around silently."""
    assert "interest_rate, debt_repayment, and" in deal.BUYER_TAX_RATE_OVERRIDE.citation
    assert "revolver_limit" in deal.BUYER_TAX_RATE_OVERRIDE.citation


def test_driver_window_choice_is_five_years_excluding_the_kenvue_transition_years():
    assert deal.BUYER_DRIVER_LOOKBACK_YEARS == 5
    assert deal.BUYER_DRIVER_EXCLUDE_YEARS == {2022, 2023}


def test_window_rationale_distinguishes_direct_evidence_from_inference():
    """The Kenvue transition-year effect on FY2023 is stated as direct; the FY2022
    vaccine/FX explanation is explicitly labelled as this file's own inference, not a
    located citation -- the two should not be presented with equal confidence."""
    r = deal.BUYER_DRIVER_WINDOW_RATIONALE
    assert "DIRECT:" in r and "INFERRED, not confirmed by a located citation:" in r
    assert "5.17-point spread" in r


def test_window_rationale_states_why_the_highest_scoring_window_was_rejected():
    """Not cherry-picking the flattering number -- the 3yr window scored higher
    (8.52%) and was rejected with a stated reason, not silently passed over."""
    assert "8.52%" in deal.BUYER_DRIVER_WINDOW_RATIONALE
    assert "bounce off FY2022's depressed base" in deal.BUYER_DRIVER_WINDOW_RATIONALE


def test_other_expense_note_grounds_the_margin_volatility_in_jnjs_own_10k():
    n = deal.JNJ_10K_FY2024_OTHER_EXPENSE_NOTE
    assert "talc matters" in n
    assert "Kenvue" in n
    assert "Shockwave" in n


def test_financing_mix_is_a_disclosure_gap_handled_as_a_sensitivity_not_a_guess():
    """J&J never disclosed the funding source. The honest response to an undisclosed
    input that drives the graded number is to span it, not to invent one split."""
    assert "never disclosed" in deal.FINANCING_MIX_NOT_DISCLOSED
    assert "SENSITIVITY, not a guess" in deal.FINANCING_MIX_NOT_DISCLOSED
    assert len(deal.FINANCING_SCENARIOS) == 3
    cash_fractions = [f for _, f, _ in deal.FINANCING_SCENARIOS]
    assert min(cash_fractions) == 0.0 and max(cash_fractions) == 1.0  # spans the range


def test_buyer_diluted_share_count_uses_the_last_pre_announcement_disclosure():
    """Same discipline as Abiomed's own figures: the last number public BEFORE the
    1 Nov 2022 trigger event, not the nearest-dated one."""
    assert deal.BUYER_DILUTED_SHARES.basis is Basis.SOURCED
    assert deal.BUYER_DILUTED_SHARES.value == 2_667.5
    assert "BEFORE the 1 November 2022 announcement" in deal.BUYER_DILUTED_SHARES.citation
    assert "nine-month average" in deal.BUYER_DILUTED_SHARES.citation


def test_forecast_base_year_predates_the_acquisition_to_avoid_circularity():
    """J&J's post-2022 results already consolidate Abiomed. Forecasting 'standalone'
    from them would put the target inside the buyer's own baseline and then add it
    again in the bridge -- a double-count, and a meaningless counterfactual."""
    assert deal.BUYER_FORECAST_BASE_YEAR == 2022
    r = deal.BUYER_FORECAST_BASE_YEAR_RATIONALE
    assert "already consolidated" in r.lower() or "ALREADY CONSOLIDATED" in r
    assert "double-counts" in r


def test_base_year_rationale_supersedes_the_earlier_window_analysis_explicitly():
    """The lookback-window work was answering the wrong question for a 2022 deal;
    saying so beats leaving two contradictory rationales in the file."""
    assert "Supersedes" in deal.BUYER_FORECAST_BASE_YEAR_RATIONALE
    assert "BUYER_DRIVER_WINDOW_RATIONALE" in deal.BUYER_FORECAST_BASE_YEAR_RATIONALE


def test_target_operating_income_is_normalised_for_the_one_time_iprd_charge():
    """Growing the reported figure projects a non-recurring charge forward forever."""
    assert deal.TARGET_NORMALISED_OPERATING_INCOME_FY2022.basis is Basis.DEMONSTRATED
    assert deal.TARGET_NORMALISED_OPERATING_INCOME_FY2022.value == pytest.approx(256.706)
    assert (deal.TARGET_NORMALISED_OPERATING_INCOME_FY2022.value
            > deal.TARGET_OPERATING_INCOME_FY2022.value)
    assert "does not recur" in deal.TARGET_NORMALISED_OPERATING_INCOME_FY2022.citation


def test_reported_operating_income_is_retained_alongside_the_normalised_figure():
    """Normalising must not destroy the as-filed number."""
    assert deal.TARGET_OPERATING_INCOME_FY2022.value == pytest.approx(140.720)
    assert deal.TARGET_OPERATING_INCOME_FY2022.basis is Basis.SOURCED


def test_fiscal_year_ends_differ_and_the_offset_is_recorded():
    """Abiomed March vs J&J December -- a nine-month offset on a ~22%-growth target."""
    assert deal.TARGET_FISCAL_YEAR_END_MONTH == 3
    assert deal.BUYER_FISCAL_YEAR_END_MONTH == 12
    assert "nine-month offset" in deal.TARGET_CALENDARIZATION_NOTE
    assert "deallab.calendarize" in deal.TARGET_CALENDARIZATION_NOTE
