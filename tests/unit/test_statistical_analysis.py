"""Tests für wiederverwendbare statistische Auswertungen."""

from dataclasses import FrozenInstanceError
from math import isfinite

import pytest

from pokemon_team_advisor.statistical_analysis import (
    CorrelationMethod,
    bootstrap_mean_difference,
    calculate_correlation,
    compare_independent_groups,
)


def test_pearson_correlation_recognizes_perfect_linear_relationship() -> None:
    result = calculate_correlation(
        [1.0, 2.0, 3.0, 4.0, 5.0],
        [2.0, 4.0, 6.0, 8.0, 10.0],
        method=CorrelationMethod.PEARSON,
    )

    assert result.method is CorrelationMethod.PEARSON
    assert result.coefficient == pytest.approx(1.0)
    assert result.p_value < 0.001
    assert result.sample_size == 5


def test_spearman_correlation_recognizes_monotonic_relationship() -> None:
    result = calculate_correlation(
        [1.0, 2.0, 3.0, 4.0, 5.0],
        [1.0, 4.0, 9.0, 16.0, 25.0],
        method=CorrelationMethod.SPEARMAN,
    )

    assert result.coefficient == pytest.approx(1.0)
    assert result.p_value < 0.001


@pytest.mark.parametrize(
    ("values_x", "values_y", "message"),
    [
        ([1.0, 2.0], [1.0], "same number"),
        ([1.0, 2.0], [2.0, 3.0], "at least three"),
        ([1.0, 2.0, float("nan")], [2.0, 3.0, 4.0], "finite"),
        ([1.0, 1.0, 1.0], [2.0, 3.0, 4.0], "constant"),
    ],
)
def test_correlation_rejects_invalid_samples(
    values_x: list[float],
    values_y: list[float],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        calculate_correlation(values_x, values_y)


def test_group_comparison_reports_welch_levene_and_effect_size() -> None:
    stronger_group = [10.0, 11.0, 12.0, 13.0, 14.0]
    weaker_group = [1.0, 2.0, 3.0, 4.0, 5.0]

    result = compare_independent_groups(stronger_group, weaker_group)

    assert result.sample_size_a == 5
    assert result.sample_size_b == 5
    assert result.mean_a == pytest.approx(12.0)
    assert result.mean_b == pytest.approx(3.0)
    assert result.mean_difference == pytest.approx(9.0)
    assert result.levene_p_value == pytest.approx(1.0)
    assert result.welch_p_value < 0.001
    assert result.hedges_g > 5.0
    assert all(
        isfinite(value)
        for value in (
            result.levene_statistic,
            result.levene_p_value,
            result.welch_t_statistic,
            result.welch_p_value,
            result.hedges_g,
        )
    )


@pytest.mark.parametrize(
    ("group_a", "group_b", "message"),
    [
        ([1.0], [2.0, 3.0], "at least two"),
        ([1.0, 2.0], [2.0, float("inf")], "finite"),
        ([1.0, 1.0], [1.0, 1.0], "pooled standard deviation"),
    ],
)
def test_group_comparison_rejects_invalid_samples(
    group_a: list[float],
    group_b: list[float],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        compare_independent_groups(group_a, group_b)


def test_bootstrap_interval_is_reproducible_and_contains_point_estimate() -> None:
    group_a = [8.0, 9.0, 10.0, 11.0, 12.0]
    group_b = [2.0, 3.0, 4.0, 5.0, 6.0]

    first = bootstrap_mean_difference(
        group_a,
        group_b,
        confidence_level=0.95,
        resamples=2_000,
        random_seed=42,
    )
    second = bootstrap_mean_difference(
        group_a,
        group_b,
        confidence_level=0.95,
        resamples=2_000,
        random_seed=42,
    )

    assert first == second
    assert first.point_estimate == pytest.approx(6.0)
    assert first.lower_bound < first.point_estimate < first.upper_bound
    assert first.confidence_level == pytest.approx(0.95)
    assert first.resamples == 2_000


@pytest.mark.parametrize(
    ("confidence_level", "resamples"),
    [
        (0.0, 1_000),
        (1.0, 1_000),
        (0.95, 0),
    ],
)
def test_bootstrap_rejects_invalid_configuration(
    confidence_level: float,
    resamples: int,
) -> None:
    with pytest.raises(ValueError):
        bootstrap_mean_difference(
            [1.0, 2.0],
            [3.0, 4.0],
            confidence_level=confidence_level,
            resamples=resamples,
        )


def test_statistical_results_are_immutable() -> None:
    result = calculate_correlation(
        [1.0, 2.0, 3.0],
        [3.0, 2.0, 1.0],
    )

    set_attribute = result.__setattr__
    with pytest.raises((FrozenInstanceError, AttributeError)):
        set_attribute("coefficient", 0.0)
