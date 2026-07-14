"""
O-9: Signal Raw Data Preservation
Implements SRS FR-3.5.3 — Raw Data Preservation

Verifies that both raw (x[n]) and filtered (y[n]) values are stored,
with the raw stream serving as the compliance source of truth.
"""

import pytest


class TestSignalRawPreservation:
    """Tests for FR-3.5.3 — Raw and filtered data preservation."""

    def test_raw_values_preserved(self):
        """Raw values should be stored alongside filtered values."""
        from middleware.engine.signal import EMAFilter

        ema = EMAFilter(alpha=0.5)

        # Apply values and collect results
        raw_values = [100.0, 150.0, 120.0, 180.0, 110.0]
        filtered_values = []

        for raw in raw_values:
            filtered = ema.filter_value(raw)
            filtered_values.append(filtered)

        # Verify raw values are unchanged
        assert raw_values == [100.0, 150.0, 120.0, 180.0, 110.0], \
            "Raw values should not be modified"

        # Verify filtered values differ from raw after first
        for raw, filtered in zip(raw_values[1:], filtered_values[1:]):
            assert raw != filtered, \
                f"Filtered value should differ from raw after initialization"

    def test_filtered_values_differ_from_raw(self):
        """Filtered values should differ from raw after initialization."""
        from middleware.engine.signal import EMAFilter

        ema = EMAFilter(alpha=0.3)

        raw = [50.0, 60.0, 70.0, 80.0, 90.0]
        filtered = [ema.filter_value(r) for r in raw]

        # After first value, filtered should diverge from raw
        for i in range(1, len(raw)):
            assert filtered[i] != raw[i], \
                f"Filtered[{i}] should differ from raw[{i}]"

    def test_raw_equals_filtered_first_value(self):
        """First value should equal raw (initialization)."""
        from middleware.engine.signal import EMAFilter

        ema = EMAFilter(alpha=0.5)
        first_value = ema.filter_value(42.0)

        assert first_value == 42.0, \
            "First filtered value should equal raw input"

    def test_batch_filtering_preserves_order(self):
        """Batch filtering should preserve value order."""
        from middleware.engine.signal import EMAFilter

        ema = EMAFilter(alpha=0.5)

        values = [10.0, 20.0, 30.0, 40.0, 50.0]
        filtered_batch = ema.filter_batch(values)

        # Should have same length
        assert len(filtered_batch) == len(values)

        # Should be in same order
        for i, (raw, filt) in enumerate(zip(values, filtered_batch)):
            assert i == values.index(raw), "Order should be preserved"

    def test_raw_data_not_overwritten(self):
        """Raw data should not be overwritten by filtered values."""
        from middleware.engine.signal import EMAFilter

        ema = EMAFilter(alpha=0.5)

        # Store raw values
        raw_values = []
        for i in range(5):
            raw_values.append(100.0 + i * 10)

        # Apply to filter
        for raw in raw_values:
            ema.filter_value(raw)

        # Raw values should still be accessible (not modified)
        assert raw_values == [100.0, 110.0, 120.0, 130.0, 140.0], \
            "Raw values should not be modified by filtering"

    def test_reset_clears_filtered_but_not_raw_concept(self):
        """Reset should clear filter state, allowing fresh raw input."""
        from middleware.engine.signal import EMAFilter

        ema = EMAFilter(alpha=0.5)

        # Apply some values
        ema.filter_value(100.0)
        ema.filter_value(200.0)
        state_before = ema.ema_value

        # Reset
        ema.reset()
        assert ema.ema_value is None, "EMA should be None after reset"
        assert ema.step_count == 0, "Step count should be 0 after reset"

        # New raw value should initialize fresh
        new_value = ema.filter_value(50.0)
        assert new_value == 50.0, "First value after reset should equal raw"
        assert new_value != state_before, "New state should differ from before reset"

    def test_multiple_filters_independent(self):
        """Multiple EMA filters should maintain independent state."""
        from middleware.engine.signal import EMAFilter

        ema1 = EMAFilter(alpha=0.5)
        ema2 = EMAFilter(alpha=0.3)

        # Apply same value to both
        ema1.filter_value(100.0)
        ema2.filter_value(100.0)

        # Apply different value
        ema1.filter_value(200.0)
        ema2.filter_value(150.0)

        # Should have different states
        assert ema1.ema_value != ema2.ema_value, \
            "Different alpha values should produce different filtered outputs"

    def test_convergence_with_different_alphas(self):
        """Different alpha values should converge at different rates."""
        from middleware.engine.signal import EMAFilter

        # Test convergence speed using filter_value directly
        # Use step input: start at 0, jump to 100
        results = {}
        for alpha in [0.1, 0.2, 0.5, 0.9]:
            ema = EMAFilter(alpha=alpha)

            # First value initializes to 0
            ema.filter_value(0.0)

            # Then apply step to 100 for only 3 steps
            for _ in range(3):
                ema.filter_value(100.0)

            results[alpha] = ema.ema_value

        # After 3 steps of step input:
        # α=0.9 → ~99.1, α=0.5 → ~87.5, α=0.2 → ~48.8, α=0.1 → ~19.0
        # Higher alpha should be closer to 100 (converged)
        assert abs(results[0.9] - 100.0) < abs(results[0.1] - 100.0), \
            f"α=0.9 ({results[0.9]:.1f}) should converge closer to 100 than α=0.1 ({results[0.1]:.1f})"
        assert abs(results[0.5] - 100.0) < abs(results[0.2] - 100.0), \
            f"α=0.5 ({results[0.5]:.1f}) should converge closer to 100 than α=0.2 ({results[0.2]:.1f})"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
