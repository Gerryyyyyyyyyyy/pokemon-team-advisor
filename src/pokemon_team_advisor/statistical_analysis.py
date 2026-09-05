"""Wiederverwendbare und validierte statistische Auswertungen."""

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from math import isfinite, sqrt
from numbers import Integral

import numpy as np
from numpy.typing import NDArray
from scipy import stats  # type: ignore[import-untyped]

type FloatArray = NDArray[np.float64]


class CorrelationMethod(StrEnum):
    """Unterstützte Korrelationsverfahren."""

    PEARSON = "pearson"
    SPEARMAN = "spearman"


@dataclass(frozen=True, slots=True)
class CorrelationResult:
    """Ergebnis einer Korrelationsanalyse."""

    method: CorrelationMethod
    coefficient: float
    p_value: float
    sample_size: int


@dataclass(frozen=True, slots=True)
class GroupComparisonResult:
    """Welch-Test, Levene-Diagnose und Effektgröße zweier Gruppen."""

    sample_size_a: int
    sample_size_b: int
    mean_a: float
    mean_b: float
    mean_difference: float
    levene_statistic: float
    levene_p_value: float
    welch_t_statistic: float
    welch_p_value: float
    hedges_g: float


@dataclass(frozen=True, slots=True)
class BootstrapInterval:
    """Perzentil-Konfidenzintervall einer Mittelwertdifferenz."""

    point_estimate: float
    lower_bound: float
    upper_bound: float
    confidence_level: float
    resamples: int


def _prepare_sample(
    values: Iterable[float],
    *,
    field: str,
    minimum_size: int,
) -> FloatArray:
    """Eine eindimensionale, endliche numerische Stichprobe validieren."""
    try:
        sample = np.asarray(list(values), dtype=np.float64)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{field} must contain only numeric values.") from error

    if sample.ndim != 1:
        raise ValueError(f"{field} must be one-dimensional.")
    if minimum_size > 0 and sample.size < minimum_size:
        number_word = "two" if minimum_size == 2 else "three"
        raise ValueError(f"{field} must contain at least {number_word} observations.")
    if not bool(np.isfinite(sample).all()):
        raise ValueError(f"{field} must contain only finite values.")

    return sample


def _require_finite_result(value: float | np.float64, *, field: str) -> float:
    """Ein Ergebnis einer externen Statistikfunktion als endlichen Float lesen."""
    result = float(value)
    if not isfinite(result):
        raise ValueError(f"Statistical result '{field}' is not finite.")
    return result


def calculate_correlation(
    values_x: Iterable[float],
    values_y: Iterable[float],
    *,
    method: CorrelationMethod = CorrelationMethod.PEARSON,
) -> CorrelationResult:
    """Pearson- oder Spearman-Korrelation zweier Messreihen berechnen."""
    if not isinstance(method, CorrelationMethod):
        raise TypeError("method must be a CorrelationMethod.")

    sample_x = _prepare_sample(values_x, field="values_x", minimum_size=0)
    sample_y = _prepare_sample(values_y, field="values_y", minimum_size=0)

    if sample_x.size != sample_y.size:
        raise ValueError("values_x and values_y must contain the same number of observations.")
    if sample_x.size < 3:
        raise ValueError("Correlation requires at least three paired observations.")
    if float(np.ptp(sample_x)) == 0.0 or float(np.ptp(sample_y)) == 0.0:
        raise ValueError("Correlation is undefined for a constant sample.")

    if method is CorrelationMethod.PEARSON:
        raw_result = stats.pearsonr(sample_x, sample_y)
    else:
        raw_result = stats.spearmanr(sample_x, sample_y)

    return CorrelationResult(
        method=method,
        coefficient=_require_finite_result(raw_result.statistic, field="coefficient"),
        p_value=_require_finite_result(raw_result.pvalue, field="p_value"),
        sample_size=int(sample_x.size),
    )


def _hedges_g(sample_a: FloatArray, sample_b: FloatArray) -> float:
    """Bias-korrigierte standardisierte Mittelwertdifferenz berechnen."""
    sample_size_a = int(sample_a.size)
    sample_size_b = int(sample_b.size)
    degrees_of_freedom = sample_size_a + sample_size_b - 2
    variance_a = float(np.var(sample_a, ddof=1))
    variance_b = float(np.var(sample_b, ddof=1))
    pooled_variance = (
        (sample_size_a - 1) * variance_a + (sample_size_b - 1) * variance_b
    ) / degrees_of_freedom

    if pooled_variance <= 0.0:
        raise ValueError("The pooled standard deviation must be greater than zero.")

    mean_difference = float(np.mean(sample_a) - np.mean(sample_b))
    cohens_d = mean_difference / sqrt(pooled_variance)
    small_sample_correction = 1.0 - 3.0 / (4.0 * degrees_of_freedom - 1.0)
    return cohens_d * small_sample_correction


def compare_independent_groups(
    group_a: Iterable[float],
    group_b: Iterable[float],
) -> GroupComparisonResult:
    """Zwei unabhängige Gruppen robust und mit Effektgröße vergleichen.

    Der Welch-t-Test wird unabhängig vom Ergebnis des Levene-Tests verwendet.
    Levene dient ausschließlich als ergänzende Varianzdiagnose.
    """
    sample_a = _prepare_sample(group_a, field="group_a", minimum_size=2)
    sample_b = _prepare_sample(group_b, field="group_b", minimum_size=2)
    hedges_g = _hedges_g(sample_a, sample_b)

    levene_result = stats.levene(sample_a, sample_b, center="median")
    welch_result = stats.ttest_ind(sample_a, sample_b, equal_var=False)
    mean_a = float(np.mean(sample_a))
    mean_b = float(np.mean(sample_b))

    return GroupComparisonResult(
        sample_size_a=int(sample_a.size),
        sample_size_b=int(sample_b.size),
        mean_a=mean_a,
        mean_b=mean_b,
        mean_difference=mean_a - mean_b,
        levene_statistic=_require_finite_result(
            levene_result.statistic,
            field="levene_statistic",
        ),
        levene_p_value=_require_finite_result(
            levene_result.pvalue,
            field="levene_p_value",
        ),
        welch_t_statistic=_require_finite_result(
            welch_result.statistic,
            field="welch_t_statistic",
        ),
        welch_p_value=_require_finite_result(
            welch_result.pvalue,
            field="welch_p_value",
        ),
        hedges_g=hedges_g,
    )


def bootstrap_mean_difference(
    group_a: Iterable[float],
    group_b: Iterable[float],
    *,
    confidence_level: float = 0.95,
    resamples: int = 10_000,
    random_seed: int | None = 0,
) -> BootstrapInterval:
    """Ein reproduzierbares Perzentilintervall der Mittelwertdifferenz schätzen."""
    if not isfinite(confidence_level) or not 0.0 < confidence_level < 1.0:
        raise ValueError("confidence_level must be finite and between zero and one.")
    if isinstance(resamples, bool) or not isinstance(resamples, Integral) or resamples <= 0:
        raise ValueError("resamples must be a positive integer.")
    if random_seed is not None and (
        isinstance(random_seed, bool) or not isinstance(random_seed, Integral)
    ):
        raise ValueError("random_seed must be an integer or None.")

    sample_a = _prepare_sample(group_a, field="group_a", minimum_size=2)
    sample_b = _prepare_sample(group_b, field="group_b", minimum_size=2)
    generator = np.random.default_rng(random_seed)
    differences = np.empty(int(resamples), dtype=np.float64)

    for index in range(int(resamples)):
        resample_a = generator.choice(sample_a, size=sample_a.size, replace=True)
        resample_b = generator.choice(sample_b, size=sample_b.size, replace=True)
        differences[index] = float(np.mean(resample_a) - np.mean(resample_b))

    alpha = (1.0 - confidence_level) / 2.0
    lower_bound, upper_bound = np.quantile(
        differences,
        [alpha, 1.0 - alpha],
    )

    return BootstrapInterval(
        point_estimate=float(np.mean(sample_a) - np.mean(sample_b)),
        lower_bound=float(lower_bound),
        upper_bound=float(upper_bound),
        confidence_level=confidence_level,
        resamples=int(resamples),
    )
