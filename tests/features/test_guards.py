"""
tests/features/test_guards.py
==============================
Unit tests cho epsilon-guard helpers trong _guards.py.
Tất cả tests phải PASS trước khi bắt đầu Phase 2.
"""
import numpy as np
import pytest

from aivitals_engine.features._guards import (
    is_degenerate,
    nan_mean,
    safe_divide,
    safe_ratio_arrays,
    safe_stat,
)

EPS = 1e-9


class TestSafeDivide:

    def test_normal_division(self):
        assert safe_divide(10.0, 2.0, epsilon=EPS) == pytest.approx(5.0)

    def test_denominator_zero_returns_nan(self):
        result = safe_divide(1.0, 0.0, epsilon=EPS)
        assert result != result  # NaN check

    def test_denominator_near_zero_returns_nan(self):
        result = safe_divide(1.0, EPS / 2, epsilon=EPS)
        assert result != result

    def test_negative_denominator_safe(self):
        assert safe_divide(-6.0, 2.0, epsilon=EPS) == pytest.approx(-3.0)

    def test_both_negative(self):
        assert safe_divide(-4.0, -2.0, epsilon=EPS) == pytest.approx(2.0)

    def test_epsilon_boundary(self):
        # Nhỏ hơn epsilon (EPS/2 < EPS) → trả NaN
        result = safe_divide(1.0, EPS / 2, epsilon=EPS)
        assert result != result  # NaN check
        # Lớn hơn epsilon → tính bình thường
        result_ok = safe_divide(1.0, EPS * 2, epsilon=EPS)
        assert np.isfinite(result_ok)

    def test_returns_float(self):
        result = safe_divide(3.0, 4.0, epsilon=EPS)
        assert isinstance(result, float)


class TestSafeRatioArrays:

    def test_equal_arrays(self):
        a = np.array([1.0, 2.0, 3.0])
        b = np.array([1.0, 2.0, 3.0])
        assert safe_ratio_arrays(a, b, epsilon=EPS) == pytest.approx(1.0)

    def test_zero_denominator_replaced(self):
        a = np.array([0.0])
        b = np.array([0.0])
        result = safe_ratio_arrays(a, b, epsilon=EPS)
        assert np.isfinite(result)  # Không crash

    def test_empty_arrays_return_nan(self):
        result = safe_ratio_arrays(np.array([]), np.array([]), epsilon=EPS)
        assert result != result  # NaN

    def test_scalar_ratio(self):
        result = safe_ratio_arrays(np.array([2.0]), np.array([4.0]), epsilon=EPS)
        assert result == pytest.approx(0.5)


class TestSafeStat:

    def test_mean_of_array(self):
        arr = np.array([1.0, 2.0, 3.0])
        assert safe_stat(arr, np.mean, min_len=1) == pytest.approx(2.0)

    def test_nan_values_excluded(self):
        arr = np.array([1.0, float("nan"), 3.0])
        assert safe_stat(arr, np.mean, min_len=1) == pytest.approx(2.0)

    def test_all_nan_returns_nan(self):
        arr = np.array([float("nan"), float("nan")])
        result = safe_stat(arr, np.mean, min_len=1)
        assert result != result  # NaN

    def test_min_len_not_met_returns_nan(self):
        arr = np.array([1.0])
        result = safe_stat(arr, np.mean, min_len=2)
        assert result != result  # NaN

    def test_empty_array_returns_nan(self):
        result = safe_stat(np.array([]), np.mean, min_len=1)
        assert result != result  # NaN

    def test_std_of_array(self):
        arr = np.array([2.0, 4.0])
        assert safe_stat(arr, np.std, min_len=2) == pytest.approx(1.0)


class TestNanMean:

    def test_normal_list(self):
        assert nan_mean([1.0, 2.0, 3.0]) == pytest.approx(2.0)

    def test_list_with_nan(self):
        assert nan_mean([1.0, float("nan"), 3.0]) == pytest.approx(2.0)

    def test_all_nan_returns_nan(self):
        result = nan_mean([float("nan"), float("nan")])
        assert result != result  # NaN

    def test_empty_list_returns_nan(self):
        result = nan_mean([])
        assert result != result  # NaN

    def test_single_value(self):
        assert nan_mean([5.0]) == pytest.approx(5.0)


class TestIsDegenerate:

    def test_empty_array(self):
        assert is_degenerate(np.array([]), min_samples=1, epsilon=EPS) is True

    def test_too_short(self):
        assert is_degenerate(np.array([1.0, 2.0]), min_samples=10, epsilon=EPS) is True

    def test_all_nan(self):
        assert is_degenerate(np.full(20, float("nan")), min_samples=10, epsilon=EPS) is True

    def test_all_inf(self):
        assert is_degenerate(np.full(20, float("inf")), min_samples=10, epsilon=EPS) is True

    def test_flat_signal(self):
        assert is_degenerate(np.ones(20), min_samples=10, epsilon=EPS) is True

    def test_valid_signal(self):
        sig = np.sin(np.linspace(0, 2 * np.pi, 240))
        assert is_degenerate(sig, min_samples=10, epsilon=EPS) is False
