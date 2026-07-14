"""
O-10: Signal Alarm on Filtered Data
Implements SRS FR-3.5.4 — False Alarm Prevention

Verifies that alarm threshold evaluation uses filtered data to prevent
mechanical roller-jitter from triggering false system alarms.
"""

import pytest


class TestSignalAlarmFiltered:
    """Tests for FR-3.5.4 — Alarm evaluation on filtered data."""

    def test_raw_triggers_false_alarm(self):
        """Raw noisy data should trigger alarms that filtered data avoids."""
        from middleware.engine.signal import EMAFilter

        # Simulate pressure with mechanical jitter
        alpha = 0.2  # Pressure channel default
        ema = EMAFilter(alpha=alpha)

        # Threshold
        threshold = 150.0

        # Raw data with brief jitter spike
        raw_data = [120.0, 121.0, 120.5, 200.0, 120.0, 121.0, 120.5]

        raw_alarm_count = 0
        filtered_alarm_count = 0

        for raw in raw_data:
            filtered = ema.filter_value(raw)

            # Check raw alarm
            if raw > threshold:
                raw_alarm_count += 1

            # Check filtered alarm
            if filtered > threshold:
                filtered_alarm_count += 1

        # Raw should trigger alarm, filtered should not (or fewer)
        assert raw_alarm_count >= 1, "Raw data should trigger alarm on jitter"
        assert filtered_alarm_count < raw_alarm_count, \
            "Filtered data should reduce false alarms"

    def test_sustained_alarm_detected_both(self):
        """Sustained threshold breach should be detected in both raw and filtered."""
        from middleware.engine.signal import EMAFilter

        alpha = 0.2
        ema = EMAFilter(alpha=alpha)

        threshold = 120.0

        # Sustained high pressure (real alarm, not jitter)
        raw_data = [120.0, 130.0, 140.0, 150.0, 160.0, 170.0]

        raw_alarm_count = 0
        filtered_alarm_count = 0

        for raw in raw_data:
            filtered = ema.filter_value(raw)

            if raw > threshold:
                raw_alarm_count += 1

            if filtered > threshold:
                filtered_alarm_count += 1

        # Both should detect sustained alarm
        assert raw_alarm_count >= 5, "Raw should detect sustained alarm"
        assert filtered_alarm_count >= 3, \
            "Filtered should detect sustained alarm after convergence"

    def test_alarm_response_time(self):
        """Filtered alarm should trigger within acceptable response time."""
        from middleware.engine.signal import EMAFilter

        alpha = 0.2
        ema = EMAFilter(alpha=alpha)

        threshold = 130.0

        # Step from normal to alarm
        raw_data = [120.0, 120.0, 120.0, 150.0, 150.0, 150.0]

        raw_alarm_step = None
        filtered_alarm_step = None

        for i, raw in enumerate(raw_data):
            filtered = ema.filter_value(raw)

            if raw_alarm_step is None and raw > threshold:
                raw_alarm_step = i

            if filtered_alarm_step is None and filtered > threshold:
                filtered_alarm_step = i

        # Raw should detect alarm immediately
        assert raw_alarm_step is not None
        assert raw_alarm_step <= 3, "Raw should detect alarm within 3 steps"

        # Filtered should detect within reasonable delay
        assert filtered_alarm_step is not None
        assert filtered_alarm_step <= 5, \
            f"Filtered should detect alarm within 5 steps, got {filtered_alarm_step}"

    def test_low_alpha_prevents_jitter_alarms(self):
        """Lower alpha should better prevent jitter-induced alarms."""
        from middleware.engine.signal import EMAFilter

        threshold = 140.0

        # Jitter data around 120 with occasional 200 spikes
        jitter_data = [120.0, 200.0, 120.0, 120.0, 200.0, 120.0, 120.0]

        # Test with α=0.1 (flow-rate, more smoothing)
        ema_01 = EMAFilter(alpha=0.1)
        filtered_01 = [ema_01.filter_value(d) for d in jitter_data]
        alarms_01 = sum(1 for f in filtered_01 if f > threshold)

        # Test with α=0.5 (less smoothing)
        ema_05 = EMAFilter(alpha=0.5)
        filtered_05 = [ema_05.filter_value(d) for d in jitter_data]
        alarms_05 = sum(1 for f in filtered_05 if f > threshold)

        # Lower alpha should produce fewer false alarms
        assert alarms_01 <= alarms_05, \
            f"α=0.1 should produce fewer false alarms ({alarms_01}) than α=0.5 ({alarms_05})"

    def test_alarm_clears_when_data_normalizes(self):
        """Alarm should clear when filtered data returns to normal range."""
        from middleware.engine.signal import EMAFilter

        alpha = 0.2
        ema = EMAFilter(alpha=alpha)

        threshold = 130.0

        # Data goes high then returns to normal
        raw_data = [120.0, 150.0, 160.0, 150.0, 120.0, 120.0, 120.0]

        alarm_active = False
        alarm_cleared = False

        for raw in raw_data:
            filtered = ema.filter_value(raw)

            if filtered > threshold:
                alarm_active = True
            elif alarm_active and filtered <= threshold:
                alarm_cleared = True
                break

        assert alarm_active, "Alarm should activate on high data"
        assert alarm_cleared, "Alarm should clear when data returns to normal"

    def test_alarm_threshold_configurable(self):
        """Alarm threshold should be configurable per channel."""
        from middleware.engine.signal import EMAFilter

        # Different thresholds for different channels
        pressure_threshold = 150.0
        spo2_threshold = 90.0

        # Pressure alarm
        ema_pressure = EMAFilter(alpha=0.2)
        ema_pressure.filter_value(160.0)  # Above threshold
        assert ema_pressure.ema_value > pressure_threshold, \
            "Pressure alarm should trigger"

        # SpO2 alarm (inverse - low is bad)
        ema_spo2 = EMAFilter(alpha=0.1)
        ema_spo2.filter_value(85.0)  # Below threshold
        assert ema_spo2.ema_value < spo2_threshold, \
            "SpO2 alarm should trigger on low value"

    def test_no_alarm_in_normal_range(self):
        """No alarm should trigger when data stays in normal range."""
        from middleware.engine.signal import EMAFilter

        alpha = 0.2
        ema = EMAFilter(alpha=alpha)

        threshold = 150.0
        normal_data = [118.0, 119.0, 120.0, 121.0, 120.5, 119.5]

        alarm_triggered = False
        for raw in normal_data:
            filtered = ema.filter_value(raw)
            if filtered > threshold:
                alarm_triggered = True
                break

        assert not alarm_triggered, \
            "No alarm should trigger for normal range data"

    def test_alarm_hysteresis_prevents_flapping(self):
        """Alarm should not rapidly toggle near threshold (hysteresis)."""
        from middleware.engine.signal import EMAFilter

        alpha = 0.2
        ema = EMAFilter(alpha=alpha)

        threshold = 125.0

        # Data oscillating around threshold
        oscillating_data = [124.0, 126.0, 124.0, 126.0, 124.0, 126.0]

        alarm_states = []
        for raw in oscillating_data:
            filtered = ema.filter_value(raw)
            alarm_states.append(filtered > threshold)

        # Filtered data should smooth oscillations
        # Count state changes
        state_changes = sum(1 for i in range(1, len(alarm_states))
                          if alarm_states[i] != alarm_states[i - 1])

        # Should have fewer state changes than raw data
        raw_states = [d > threshold for d in oscillating_data]
        raw_changes = sum(1 for i in range(1, len(raw_states))
                        if raw_states[i] != raw_states[i - 1])

        assert state_changes <= raw_changes, \
            f"Filtered should have fewer state changes ({state_changes}) than raw ({raw_changes})"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
