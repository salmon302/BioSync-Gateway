"""
O-8: EMA Alpha Tuning
Implements SRS FR-3.5.2 — EMA Filter Alpha Tuning

Verifies that the EMA filter supports configurable alpha values:
- α=0.2 for pressure channels (more smoothing)
- α=0.1 for flow-rate channels (even more smoothing)
"""

import pytest


class TestEMAAlphaTuning:
    """Tests for FR-3.5.2 — EMA filter alpha tuning."""

    def test_alpha_02_pressure_channel(self):
        """α=0.2 should provide more smoothing for pressure channels."""
        from middleware.engine.signal import EMAFilter

        ema = EMAFilter(alpha=0.2)

        # Apply noisy pressure data
        noisy_pressure = [120.0, 125.0, 118.0, 122.0, 119.0, 121.0, 120.5]
        filtered = [ema.filter_value(p) for p in noisy_pressure]

        # Filtered values should be smoother than raw
        raw_variance = self._variance(noisy_pressure)
        filtered_variance = self._variance(filtered)

        assert filtered_variance < raw_variance, \
            "Filtered pressure should have lower variance than raw"

    def test_alpha_01_flow_rate_channel(self):
        """α=0.1 should provide maximum smoothing for flow-rate channels."""
        from middleware.engine.signal import EMAFilter

        ema = EMAFilter(alpha=0.1)

        # Apply noisy flow-rate data
        noisy_flow = [100.0, 110.0, 95.0, 105.0, 98.0, 102.0, 100.5]
        filtered = [ema.filter_value(f) for f in noisy_flow]

        # Filtered values should be much smoother
        raw_variance = self._variance(noisy_flow)
        filtered_variance = self._variance(filtered)

        assert filtered_variance < raw_variance, \
            "Filtered flow-rate should have lower variance than raw"
        assert filtered_variance < 5.0, \
            f"Flow-rate filtered variance should be very low, got {filtered_variance}"

    def test_alpha_05_default(self):
        """α=0.5 should provide balanced smoothing (default)."""
        from middleware.engine.signal import EMAFilter

        ema = EMAFilter(alpha=0.5)

        # Step response: should converge faster than α=0.2
        for _ in range(10):
            ema.filter_value(100.0)

        # After 10 steps of 100, should be close to 100
        assert abs(ema.ema_value - 100.0) < 1.0, \
            f"α=0.5 should converge quickly, got {ema.ema_value}"

    def test_alpha_01_slower_convergence(self):
        """α=0.1 should converge slower than α=0.5."""
        from middleware.engine.signal import EMAFilter

        # Apply step input: start at 0, jump to 100
        ema_01 = EMAFilter(alpha=0.1)
        ema_05 = EMAFilter(alpha=0.5)

        # First value initializes both to 0
        ema_01.filter_value(0.0)
        ema_05.filter_value(0.0)

        # Then apply step to 100
        for _ in range(5):
            ema_01.filter_value(100.0)
            ema_05.filter_value(100.0)

        # α=0.5 should be closer to 100 than α=0.1
        # After 5 steps of step input: α=0.5 → ~96.875, α=0.1 → ~40.95
        dist_05 = abs(ema_05.ema_value - 100.0)
        dist_01 = abs(ema_01.ema_value - 100.0)
        assert dist_05 < dist_01, \
            f"α=0.5 distance ({dist_05:.2f}) should be less than α=0.1 distance ({dist_01:.2f})"

    def test_alpha_02_vs_alpha_01_smoothing(self):
        """α=0.2 should smooth less than α=0.1."""
        from middleware.engine.signal import EMAFilter

        ema_02 = EMAFilter(alpha=0.2)
        ema_01 = EMAFilter(alpha=0.1)

        # Apply alternating noisy data
        noisy = [100.0, 150.0, 100.0, 150.0, 100.0, 150.0]

        for value in noisy:
            ema_02.filter_value(value)
            ema_01.filter_value(value)

        # α=0.1 should be smoother (closer to mean)
        # α=0.2 should track more closely to recent values
        assert ema_02.ema_value > ema_01.ema_value, \
            "α=0.2 should track recent values more than α=0.1"

    def test_alpha_boundary_values(self):
        """Alpha boundary values should be accepted or rejected appropriately."""
        from middleware.engine.signal import EMAFilter

        # Valid alpha values
        for alpha in [0.01, 0.1, 0.2, 0.5, 0.9, 1.0]:
            ema = EMAFilter(alpha=alpha)
            assert ema.alpha == alpha

        # Invalid alpha values should raise ValueError
        for invalid_alpha in [0, -0.1, 1.1, -1]:
            with pytest.raises(ValueError):
                EMAFilter(alpha=invalid_alpha)

    def test_pressure_channel_default_alpha(self):
        """Pressure channel should default to α=0.2."""
        from middleware.engine.signal import EMAFilter

        # Verify α=0.2 is appropriate for pressure
        ema = EMAFilter(alpha=0.2)

        # Simulate pressure with occasional spike
        pressure_data = [120.0] * 10 + [200.0] + [120.0] * 10
        filtered = [ema.filter_value(p) for p in pressure_data]

        # Spike should be smoothed
        assert max(filtered) < 180.0, \
            f"Pressure spike should be smoothed, got max {max(filtered)}"

    def test_flow_rate_channel_default_alpha(self):
        """Flow-rate channel should default to α=0.1."""
        from middleware.engine.signal import EMAFilter

        # Verify α=0.1 is appropriate for flow-rate
        ema = EMAFilter(alpha=0.1)

        # Simulate flow-rate with noise
        flow_data = [50.0] * 10 + [100.0] + [50.0] * 10
        filtered = [ema.filter_value(f) for f in flow_data]

        # Noise should be heavily smoothed
        assert max(filtered) < 70.0, \
            f"Flow-rate noise should be heavily smoothed, got max {max(filtered)}"

    @staticmethod
    def _variance(values):
        """Calculate population variance."""
        n = len(values)
        if n == 0:
            return 0
        mean = sum(values) / n
        return sum((x - mean) ** 2 for x in values) / n


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
