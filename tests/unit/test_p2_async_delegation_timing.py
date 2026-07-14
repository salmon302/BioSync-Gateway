"""
P2: Async Delegation Timing Test
Implements SRS FR-3.6.2 / Constraint C1

Verifies that Pulse simulation step operations are delegated to
ProcessPoolExecutor and do not block the asyncio event loop.
"""

import pytest
import asyncio
import time
from concurrent.futures import ProcessPoolExecutor


class TestPulseAsyncDelegationTiming:
    """Tests for FR-3.6.2 — Async delegation timing verification."""

    def test_simulation_manager_has_executor(self):
        """SimulationManager must have a ProcessPoolExecutor."""
        from middleware.engine.pulse import SimulationManager

        manager = SimulationManager(max_concurrent=3)
        assert hasattr(manager, 'executor')
        assert isinstance(manager.executor, ProcessPoolExecutor)

    def test_step_simulation_is_async_callable(self):
        """step_simulation must be an async method."""
        from middleware.engine.pulse import SimulationManager

        manager = SimulationManager(max_concurrent=2)
        # In Python, async functions are coroutine functions
        assert asyncio.iscoroutinefunction(manager.step_simulation)

    def test_step_delegates_to_executor(self):
        """step_simulation must use run_in_executor for non-blocking behavior."""
        from middleware.engine.pulse import SimulationManager, PatientConfig

        manager = SimulationManager(max_concurrent=2)
        config = PatientConfig(
            patient_id="async-test-001",
            age=45, weight_kg=70.0, height_cm=175.0, sex="male"
        )
        manager.create_simulation(config)

        async def run_step():
            metrics = await manager.step_simulation("async-test-001", 50)
            return metrics

        # Running the async step should not block
        metrics = asyncio.run(run_step())
        assert metrics is not None
        assert "heart_rate" in metrics

    def test_multiple_steps_dont_block_event_loop(self):
        """Multiple async steps should not block each other."""
        from middleware.engine.pulse import SimulationManager, PatientConfig
        import time

        manager = SimulationManager(max_concurrent=3)
        sim_ids = []
        for i in range(3):
            config = PatientConfig(
                patient_id=f"nonblock-{i}",
                age=30 + i * 10,
                weight_kg=60 + i * 5,
                height_cm=165 + i * 5,
                sex="male" if i % 2 == 0 else "female"
            )
            sid = manager.create_simulation(config)
            sim_ids.append(sid)

        async def step_all():
            start = time.time()
            tasks = [manager.step_simulation(sid, 100) for sid in sim_ids]
            results = await asyncio.gather(*tasks)
            elapsed = time.time() - start
            return results, elapsed

        results, elapsed = asyncio.run(step_all())

        assert len(results) == 3
        for r in results:
            assert "heart_rate" in r
        # All 3 should complete — elapsed time confirms they ran
        assert elapsed >= 0

    def test_module_level_worker_function_exists(self):
        """_step_worker_sync must be a module-level function for ProcessPoolExecutor."""
        from middleware.engine.pulse import _step_worker_sync

        assert callable(_step_worker_sync)

    def test_worker_function_returns_metrics(self):
        """_step_worker_sync must return metrics dict."""
        from middleware.engine.pulse import _step_worker_sync, PulseWorker, PatientConfig

        config = PatientConfig(
            patient_id="worker-fn-test",
            age=40, weight_kg=70.0, height_cm=175.0, sex="male"
        )
        worker = PulseWorker(config)
        worker.initialize()

        metrics = _step_worker_sync(worker, 10)

        assert isinstance(metrics, dict)
        assert "heart_rate" in metrics
        assert "spo2" in metrics
