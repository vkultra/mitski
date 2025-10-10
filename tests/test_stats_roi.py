"""Tests for ROI helpers."""

from services.stats.roi import allocate_general_costs, compute_roi


def test_compute_roi_positive() -> None:
    roi = compute_roi(20000, 10000)
    assert roi == 1.0


def test_compute_roi_without_cost() -> None:
    assert compute_roi(10000, 0) is None


def test_allocate_general_costs_proportional() -> None:
    allocation = allocate_general_costs(1000, {1: 2000, 2: 1000})
    assert allocation[1] + allocation[2] == 1000
    assert allocation[1] > allocation[2]


def test_allocate_general_costs_zero_revenue() -> None:
    allocation = allocate_general_costs(1000, {1: 0, 2: 0})
    assert allocation == {1: 500, 2: 500}
