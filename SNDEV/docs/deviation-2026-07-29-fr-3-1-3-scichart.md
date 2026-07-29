Title: deviation-fr-3-1-3-scichart-removal
Date: 2026-07-29T18:30:00Z
Author: Seth Nenninger (tencent/hy3 Agent)
Contribution Type: Implementation
Ticket/Context: SRS FR-3.1.3 / NFR-M2; documentation-integrity repair. The code comment in `frontend/src/providers/chart-provider.tsx` and `DEVELOPMENT_PLAN.md` cite `REMAINING_WORK.md §0` as the home of the approved SciChart deviation, but `REMAINING_WORK.md` (and `REMAINING_WORK_v1.1.md`) were deleted from the repo. This register re-establishes the authoritative deviation record for CSV traceability.
Summary: Formal deviation from SRS FR-3.1.3 / NFR-M2 — the SciChart.js enterprise rendering backend is removed; Apache ECharts 5 (Canvas) is the sole backend. The provider-abstraction interface is retained so a future backend can be added without touching consumers.
Status: APPROVED AS A FORMAL DEVIATION (recorded 2026-07-29; supersedes the deleted `REMAINING_WORK.md` reference).

# Formal Deviation Record — FR-3.1.3 / NFR-M2 (SciChart.js backend removed)

## 1. Requirement as Written (SRS v1.1)
- **FR-3.1.3:** "The frontend shall support Apache ECharts (open-source path) and SciChart.js (enterprise path) as swappable rendering backends via a chart-provider abstraction interface."
- **NFR-M2:** "Chart rendering backend (ECharts vs. SciChart.js) shall be swappable via a provider abstraction without changing consuming components."

## 2. Observed Implementation
- `frontend/src/providers/chart-provider.tsx` — the `ChartConfig.type` is typed as `'echarts'` only; the `ECharts` import is hard-bound and `createChart` calls `echarts.init(...)`. There is no SciChart import, dependency, or code path anywhere in `frontend/` (repo-wide grep for `scichart` returns a single hit — the comment in this file).
- `frontend/package.json` dependencies contain `echarts` only; `scichart` is absent. SciChart.js is a commercial/licensed dependency and was never added.
- The abstraction interface (`ChartProvider` / `useChart` with `createChart` / `updateData` / `dispose`) is fully retained, so the *mechanism* for swapping remains; only the second concrete backend is not present.

## 3. Root-Cause / Justification
- SciChart.js is a paid enterprise library; adopting it would introduce a licensing obligation and a heavyweight WASM/WebGL dependency for a benefit (very-high-point-count enterprise charting) not required to meet the SRS performance envelope.
- `DEVELOPMENT_PLAN.md §7.1 Risk #3 (2026-07-23 note)` already records the decision: "SciChart.js has been removed from the tech stack per an approved deviation from SRS FR-3.1.3. Apache ECharts 5 (Canvas-based) is the sole charting backend. ECharts meets the 60 fps / 100k pts/s target for the telemetry dashboard when combined with LTTB downsampling." The decision predates the deletion of `REMAINING_WORK.md`, which only *narrated* the rationale.
- The SRS FR-3.1.1 permits "an HTML5 Canvas or WebGL context." ECharts renders to Canvas by default, so the hard rendering requirement (Canvas/WebGL, non-SVG) is still satisfied. Only the *second, optional* enterprise backend is dropped.

## 4. Deviation
- **Original requirement:** two swappable backends (ECharts + SciChart.js) present at runtime.
- **Deviated (validated) requirement:** one supported backend (Apache ECharts 5, Canvas), with the provider-abstraction interface retained for future backend addition.
- This is a runtime/scope reduction, not a behavioral regression: all consuming components (TelemetryDashboard, etc.) continue to work unchanged through the abstraction.

## 5. Impact Assessment
- **Functional:** None for the open-source deployment path. ECharts meets FR-3.1.1 (Canvas, non-SVG), FR-3.1.2/3.1.6 (zoom/pan via `dataZoom`), and NFR-P2 (60 fps with LTTB downsampling).
- **Safety / Efficacy:** Negligible. Telemetry alarm evaluation is server-side (EMA-filtered, FR-3.5.4); the chart is a visualization surface.
- **Regulatory (CSV / 21 CFR Part 11):** Deviation is documented, justified, and traceable. NFR-M2's "swappable without changing consuming components" is preserved at the *interface* level; SRS §8 traceability for FR-3.1.3 should note the deviation ID.
- **Licensing:** Positive — removes a commercial dependency from the OSS project.

## 6. Remediation (if strict two-backend compliance is later mandated)
- Add `scichart` to `frontend/package.json`, implement a `scichart` branch in `chart-provider.tsx` (`createChart` returns a SciChart `ECharts`/`SciChart` instance), and select via `VITE_CHART_PROVIDER` env. No consumer changes required because the `ChartConfig`/`useChart` surface is already stable. Requires procurement of a SciChart license.

## 7. Disposition
- **Status:** APPROVED AS A FORMAL DEVIATION.
- **Effective configuration:** `ChartConfig.type = 'echarts'` only; SciChart.js not bundled.
- **Reference implementation:** `frontend/src/providers/chart-provider.tsx` (header comment updated to cite this document).
- **Companion records:** `DEVELOPMENT_PLAN.md §7.1 Risk #3`; consolidated status log `SNDEV/docs/impl-2026-07-29-srs-status-and-remaining-work.md`.
- **Action item:** SRS §8 traceability row for FR-3.1.3 should carry a footnote to this deviation once the SRS is next revised.

(No secrets/tokens recorded.)
