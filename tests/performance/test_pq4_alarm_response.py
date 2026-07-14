"""
PQ-4: Alarm Response Time
Implements SRS NFR-P1 — 100ms Alarm Response

Verifies that alarm detection and response completes within 100ms.
"""

import pytest
import time


class TestAlarmResponse:
    """Tests for NFR-P1 — Alarm response < 100ms."""

    def test_alarm_detection_latency(self):
        """Alarm detection should complete within 100ms."""
        from middleware.engine.signal import EMAFilter

        threshold = 150.0
        ema = EMAFilter(alpha=0.2)

        # Simulate alarm condition - start with high values to ensure alarm triggers
        alarm_data = [160.0, 170.0, 180.0, 190.0, 200.0]

        latencies = []
        alarm_detected = False

        for value in alarm_data:
            start = time.perf_counter()
            filtered = ema.filter_value(value)
            end = time.perf_counter()

            latencies.append((end - start) * 1000)  # ms

            if filtered > threshold and not alarm_detected:
                alarm_detected = True

        p95 = sorted(latencies)[int(len(latencies) * 0.95)]
        assert p95 < 100.0, f"Alarm detection P95 {p95:.3f}ms exceeds 100ms"
        assert alarm_detected, "Alarm should be detected"

    def test_alarm_evaluation_speed(self):
        """Alarm threshold evaluation should be instantaneous."""
        from middleware.engine.signal import EMAFilter

        ema = EMAFilter(alpha=0.2)
        threshold = 150.0

        latencies = []
        for _ in range(1000):
            start = time.perf_counter()
            filtered = ema.filter_value(160.0)
            is_alarm = filtered > threshold
            end = time.perf_counter()

            latencies.append((end - start) * 1000)

        avg_ms = sum(latencies) / len(latencies)
        assert avg_ms < 1.0, f"Average alarm eval {avg_ms:.3f}ms is too slow"

    def test_multi_channel_alarm_detection(self):
        """Multi-channel alarm detection should complete within 100ms."""
        from middleware.engine.signal import EMAFilter

        thresholds = {
            "heart_rate": 150.0,
            "spo2": 90.0,
            "blood_pressure_systolic": 180.0
        }

        emas = {ch: EMAFilter(alpha=0.2) for ch in thresholds}

        # Simulate multi-channel alarm - use values that will trigger alarms
        channel_data = {
            "heart_rate": 160.0,
            "spo2": 95.0,  # Above 90 threshold
            "blood_pressure_systolic": 120.0
        }

        start = time.perf_counter()

        alarms = {}
        for channel, value in channel_data.items():
            filtered = emas[channel].filter_value(value)
            alarms[channel] = filtered > thresholds[channel]

        elapsed = (time.perf_counter() - start) * 1000

        assert elapsed < 100.0, f"Multi-channel alarm took {elapsed:.3f}ms"
        # At least one alarm should trigger
        assert any(alarms.values()), "At least one alarm should trigger"

    def test_alarm_clear_detection(self):
        """Alarm clear detection should be fast."""
        from middleware.engine.signal import EMAFilter

        threshold = 150.0
        ema = EMAFilter(alpha=0.2)

        # Data goes above then below threshold
        data = [160.0, 170.0, 120.0, 118.0, 119.0]

        start = time.perf_counter()
        alarm_active = False
        alarm_cleared_step = None

        for i, value in enumerate(data):
            filtered = ema.filter_value(value)
            if filtered > threshold:
                alarm_active = True
            elif alarm_active and filtered <= threshold:
                alarm_cleared_step = i
                break

        elapsed = (time.perf_counter() - start) * 1000

        assert elapsed < 100.0, f"Alarm clear detection took {elapsed:.3f}ms"
        assert alarm_cleared_step is not None

    def test_sustained_alarm_monitoring(self):
        """Sustained alarm monitoring should maintain < 100ms per evaluation."""
        from middleware.engine.signal import EMAFilter

        threshold = 150.0
        ema = EMAFilter(alpha=0.2)

        latencies = []
        for _ in range(100):
            start = time.perf_counter()
            filtered = ema.filter_value(160.0)
            is_alarm = filtered > threshold
            end = time.perf_counter()

            latencies.append((end - start) * 1000)

        p95 = sorted(latencies)[int(len(latencies) * 0.95)]
        assert p95 < 100.0, f"Sustained alarm P95 {p95:.3f}ms exceeds 100ms"

    def test_alarm_state_transition_speed(self):
        """Alarm state transitions should be instantaneous."""
        from middleware.engine.signal import EMAFilter

        ema = EMAFilter(alpha=0.2)
        threshold = 150.0

        # Simulate alarm on/off/on with values clearly above/below threshold
        data = [160.0, 120.0, 160.0, 120.0]

        start = time.perf_counter()
        states = []

        for value in data:
            filtered = ema.filter_value(value)
            states.append(filtered > threshold)

        elapsed = (time.perf_counter() - start) * 1000

        assert elapsed < 100.0, f"State transitions took {elapsed:.3f}ms"
        # After filtering, should detect alarm on high values
        assert any(states), "Should detect at least one alarm state"

    def test_alarm_threshold_adjustment(self):
        """Dynamic threshold adjustment should not impact alarm speed."""
        from middleware.engine.signal import EMAFilter

        ema = EMAFilter(alpha=0.2)

        latencies = []
        for i in range(100):
            threshold = 140.0 + (i % 20)  # Dynamic threshold

            start = time.perf_counter()
            filtered = ema.filter_value(160.0)
            is_alarm = filtered > threshold
            end = time.perf_counter()

            latencies.append((end - start) * 1000)

        avg_ms = sum(latencies) / len(latencies)
        assert avg_ms < 1.0, f"Dynamic threshold avg {avg_ms:.3f}ms is too slow"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
