# SPDX-License-Identifier: MIT
"""
OQ-17: LTTB Downsampling Engine
Implements SRS FR-3.1.2 — 60 fps at 100k pts/s via LTTB downsampling.

Validates that the LTTB algorithm:
- Preserves first and last points
- Preserves visual peaks and troughs
- Produces output <= threshold
- Handles edge cases (empty, small data, threshold >= n)
"""

import pytest
import math


class TestLTTB:
    """Tests for LTTB downsampling engine."""

    def test_preserves_first_and_last_points(self):
        """LTTB must always include the first and last data points."""
        from middleware.engine.lttb import lttb

        data = [(float(i), float(i * 2)) for i in range(100)]
        result = lttb(data, threshold=10)

        assert len(result) == 10
        assert result[0] == data[0]
        assert result[-1] == data[-1]

    def test_output_size_leq_threshold(self):
        """Output must never exceed the threshold."""
        from middleware.engine.lttb import lttb

        data = [(float(i), float(i)) for i in range(1000)]
        for threshold in [5, 10, 50, 100, 500]:
            result = lttb(data, threshold)
            assert len(result) <= threshold, (
                f"threshold={threshold}: got {len(result)} points"
            )

    def test_preserves_peaks_and_troughs(self):
        """LTTB must preserve local maxima and minima (anomalies)."""
        from middleware.engine.lttb import lttb

        # Create a sine wave with a sharp spike
        data = []
        for i in range(200):
            y = math.sin(i * 0.1)
            if i == 100:
                y = 10.0  # Sharp spike (anomaly)
            data.append((float(i), y))

        result = lttb(data, threshold=20)

        # The spike at i=100 should be preserved
        spike_preserved = any(abs(p[0] - 100.0) < 1.0 for p in result)
        assert spike_preserved, "LTTB did not preserve the spike at i=100"

    def test_threshold_geq_n_returns_all(self):
        """When threshold >= data length, return all points."""
        from middleware.engine.lttb import lttb

        data = [(float(i), float(i)) for i in range(50)]
        result = lttb(data, threshold=100)
        assert len(result) == 50

    def test_threshold_lt_2_returns_all(self):
        """When threshold < 2, return all points (can't downsample meaningfully)."""
        from middleware.engine.lttb import lttb

        data = [(float(i), float(i)) for i in range(50)]
        result = lttb(data, threshold=1)
        assert len(result) == 50

    def test_empty_data(self):
        """Empty input returns empty output."""
        from middleware.engine.lttb import lttb

        result = lttb([], threshold=10)
        assert result == []

    def test_single_point(self):
        """Single point returns single point."""
        from middleware.engine.lttb import lttb

        result = lttb([(1.0, 2.0)], threshold=10)
        assert result == [(1.0, 2.0)]

    def test_two_points(self):
        """Two points return both regardless of threshold."""
        from middleware.engine.lttb import lttb

        data = [(1.0, 2.0), (3.0, 4.0)]
        result = lttb(data, threshold=10)
        assert result == data

    def test_downsample_telemetry_preserves_order(self):
        """downsample_telemetry must preserve timestamp ordering."""
        from middleware.engine.lttb import downsample_telemetry

        data = [{"timestamp": float(i), "value": float(i)} for i in range(500)]
        result = downsample_telemetry(data, threshold=50)

        timestamps = [d["timestamp"] for d in result]
        assert timestamps == sorted(timestamps)

    def test_large_dataset_performance(self):
        """100k points should downsample in < 1 second."""
        import time
        from middleware.engine.lttb import lttb

        data = [(float(i), float(i * 0.001)) for i in range(100000)]

        start = time.perf_counter()
        result = lttb(data, threshold=2000)
        elapsed = time.perf_counter() - start

        assert len(result) <= 2000
        assert elapsed < 1.0, f"LTTB on 100k points took {elapsed:.3f}s (target < 1s)"
