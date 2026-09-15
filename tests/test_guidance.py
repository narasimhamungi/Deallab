import pytest

from deallab.deals import jnj_abiomed
from deallab.guidance import GuidanceReport, check_point, check_range


def test_a_modelled_figure_inside_the_guided_range_passes():
    c = check_range("Year 1 adjusted EPS", "adjusted", "slightly dilutive to neutral",
                    *jnj_abiomed.GUIDANCE_YEAR_ONE_BOUNDS, modelled=-0.004)
    assert c.within
    assert "does not make the assumptions correct" in c.reading


def test_a_miss_is_reported_as_a_finding_and_explicitly_not_to_be_tuned_away():
    c = check_range("Year 1 adjusted EPS", "adjusted", "slightly dilutive to neutral",
                    *jnj_abiomed.GUIDANCE_YEAR_ONE_BOUNDS, modelled=0.05)
    assert not c.within
    assert "Do not tune an input" in c.reading
    assert c.gap == pytest.approx(0.05 - jnj_abiomed.GUIDANCE_YEAR_ONE_BOUNDS[1])


def test_point_check_uses_an_explicit_tolerance_rather_than_defining_its_own_pass_mark():
    tight = check_point("2024 accretion", "adjusted", "approximately $0.05",
                        jnj_abiomed.GUIDANCE_2024_ACCRETION_USD, 0.08, tolerance=0.01)
    loose = check_point("2024 accretion", "adjusted", "approximately $0.05",
                        jnj_abiomed.GUIDANCE_2024_ACCRETION_USD, 0.08, tolerance=0.05)
    assert not tight.within and loose.within


def test_report_warns_against_treating_a_full_match_as_success():
    r = GuidanceReport((check_range("x", "adjusted", "g", -0.01, 0.01, 0.0),))
    assert r.all_within
    assert "viewed with suspicion" in r.format()
