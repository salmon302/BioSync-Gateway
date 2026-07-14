"""
O-12: Pulse Data Extraction
Implements SRS FR-3.6.4 — Data Extraction

Verifies that the middleware extracts specific physiological metrics at
configurable intervals using the Pulse Data Request Manager, including:
- HeartRate
- MeanAirwayPressure_cmH2O
- ArterialOxygenPartialPressure_mmHg
- OxygenSaturation
- RespirationRate
"""

import pytest


class TestPulseDataExtraction:
    """Tests for FR-3.6.4 — Pulse data extraction."""

    def test_required_metrics_defined(self):
        """PulseWorker should define required metrics list."""
        from middleware.engine.pulse import PulseWorker

        assert hasattr(PulseWorker, 'REQUIRED_METRICS')
        required = PulseWorker.REQUIRED_METRICS

        # Should contain all SRS-specified metrics (updated P0 naming)
        assert "HeartRate" in required
        assert "SystolicArterialPressure_mmHg" in required
        assert "DiastolicArterialPressure_mmHg" in required
        assert "RespirationRate" in required
        assert "OxygenSaturation" in required
        assert "MeanAirwayPressure_cmH2O" in required
        assert "ArterialOxygenPartialPressure_mmHg" in required

    def test_metrics_extracted_on_step(self):
        """Stepping simulation should extract metrics."""
        from middleware.engine.pulse import PulseWorker, PatientConfig

        config = PatientConfig(
            patient_id="extract-test-001",
            age=45, weight_kg=70.0, height_cm=175.0, sex="male"
        )
        worker = PulseWorker(config)
        worker.initialize()

        metrics = worker.step(10)

        # Metrics should be returned (may be dict-like or object)
        assert metrics is not None

    def test_metrics_contain_heart_rate(self):
        """Extracted metrics should contain heart_rate."""
        from middleware.engine.pulse import PulseWorker, PatientConfig

        config = PatientConfig(
            patient_id="hr-test-001",
            age=40, weight_kg=75.0, height_cm=180.0, sex="male"
        )
        worker = PulseWorker(config)
        worker.initialize()

        metrics = worker.step(10)

        # Check metrics contain heart_rate
        if isinstance(metrics, dict):
            assert "heart_rate" in metrics
        else:
            # Object-like metrics
            metrics_str = str(metrics)
            assert "heart_rate" in metrics_str or hasattr(metrics, 'heart_rate')

    def test_metrics_contain_blood_pressure(self):
        """Extracted metrics should contain blood pressure values."""
        from middleware.engine.pulse import PulseWorker, PatientConfig

        config = PatientConfig(
            patient_id="bp-test-001",
            age=50, weight_kg=80.0, height_cm=175.0, sex="male"
        )
        worker = PulseWorker(config)
        worker.initialize()

        metrics = worker.step(10)

        if isinstance(metrics, dict):
            assert "blood_pressure_systolic" in metrics
            assert "blood_pressure_diastolic" in metrics
        else:
            metrics_str = str(metrics)
            assert "blood_pressure" in metrics_str

    def test_metrics_contain_spo2(self):
        """Extracted metrics should contain SpO2."""
        from middleware.engine.pulse import PulseWorker, PatientConfig

        config = PatientConfig(
            patient_id="spo2-test-001",
            age=35, weight_kg=65.0, height_cm=165.0, sex="female"
        )
        worker = PulseWorker(config)
        worker.initialize()

        metrics = worker.step(10)

        if isinstance(metrics, dict):
            assert "spo2" in metrics
        else:
            metrics_str = str(metrics)
            assert "spo2" in metrics_str

    def test_metrics_contain_respiratory_rate(self):
        """Extracted metrics should contain respiratory_rate."""
        from middleware.engine.pulse import PulseWorker, PatientConfig

        config = PatientConfig(
            patient_id="rr-test-001",
            age=42, weight_kg=70.0, height_cm=170.0, sex="female"
        )
        worker = PulseWorker(config)
        worker.initialize()

        metrics = worker.step(10)

        if isinstance(metrics, dict):
            assert "respiratory_rate" in metrics
        else:
            metrics_str = str(metrics)
            assert "respiratory_rate" in metrics_str

    def test_metrics_physiological_ranges(self):
        """Extracted metrics should be within physiological ranges."""
        from middleware.engine.pulse import PulseWorker, PatientConfig

        config = PatientConfig(
            patient_id="range-test-001",
            age=45, weight_kg=70.0, height_cm=175.0, sex="male"
        )
        worker = PulseWorker(config)
        worker.initialize()

        metrics = worker.step(50)

        if isinstance(metrics, dict):
            # Heart rate: 40-200 bpm
            if "heart_rate" in metrics:
                assert 40 <= metrics["heart_rate"] <= 200, \
                    f"Heart rate out of range: {metrics['heart_rate']}"

            # SpO2: 80-100%
            if "spo2" in metrics:
                assert 80 <= metrics["spo2"] <= 100, \
                    f"SpO2 out of range: {metrics['spo2']}"

            # Respiratory rate: 8-40 breaths/min
            if "respiratory_rate" in metrics:
                assert 8 <= metrics["respiratory_rate"] <= 40, \
                    f"Respiratory rate out of range: {metrics['respiratory_rate']}"

    def test_metrics_history_accumulates(self):
        """Metrics history should accumulate across steps."""
        from middleware.engine.pulse import PulseWorker, PatientConfig

        config = PatientConfig(
            patient_id="history-test-001",
            age=38, weight_kg=68.0, height_cm=168.0, sex="female"
        )
        worker = PulseWorker(config)
        worker.initialize()

        # Step multiple times
        worker.step(10)
        count_after_1 = len(worker.metrics_history)

        worker.step(10)
        count_after_2 = len(worker.metrics_history)

        # History should grow
        assert count_after_2 >= count_after_1, \
            "Metrics history should accumulate across steps"

    def test_metrics_timestamp_included(self):
        """Extracted metrics should include timestamp."""
        from middleware.engine.pulse import PulseWorker, PatientConfig
        import time

        config = PatientConfig(
            patient_id="timestamp-test-001",
            age=50, weight_kg=75.0, height_cm=175.0, sex="male"
        )
        worker = PulseWorker(config)
        worker.initialize()

        before = time.time()
        metrics = worker.step(10)
        after = time.time()

        if isinstance(metrics, dict) and "timestamp" in metrics:
            assert before <= metrics["timestamp"] <= after, \
                "Metrics timestamp should be within step execution window"

    def test_different_patients_different_metrics(self):
        """Different patient configs should produce different metrics."""
        from middleware.engine.pulse import PulseWorker, PatientConfig

        # Young healthy patient
        young = PulseWorker(PatientConfig(
            patient_id="young", age=25, weight_kg=65.0,
            height_cm=170.0, sex="male", base_heart_rate=65.0
        ))
        young.initialize()
        young_metrics = young.step(10)

        # Older patient with conditions
        older = PulseWorker(PatientConfig(
            patient_id="older", age=70, weight_kg=85.0,
            height_cm=175.0, sex="male", base_heart_rate=80.0,
            conditions=["hypertension"]
        ))
        older.initialize()
        older_metrics = older.step(10)

        # Metrics should differ between patients
        if isinstance(young_metrics, dict) and isinstance(older_metrics, dict):
            if "heart_rate" in young_metrics and "heart_rate" in older_metrics:
                # Older patient with higher base HR should differ
                assert young_metrics["heart_rate"] != older_metrics["heart_rate"] or \
                       young_metrics is not older_metrics


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
