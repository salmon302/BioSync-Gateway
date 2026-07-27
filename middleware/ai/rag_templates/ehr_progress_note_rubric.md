# SPDX-License-Identifier: MIT
# EHR Progress-Note Rubric
#
# Static RAG template (FR-3.15.3 / C9). Used by the Pulse -> progress-note
# synthesis endpoint (FR-3.15.4) as the RAG context guiding how to render
# aggregated numeric telemetry into an unstructured, EHR-ingestible note.

# TEMPLATE TYPE: ehr_rubric
# DESCRIPTION: EHR progress-note writing rubric (SOAP, abbreviations)

EHR PROGRESS NOTE RUBRIC
=======================

Goal: convert aggregated simulator telemetry into a concise, unstructured
progress note suitable for downstream EHR text ingestion testing (FR-3.15.4).

STRUCTURE (SOAP)
  - Subjective (S): brief narrative context; simulated patient state.
  - Objective (O): the aggregated vitals/channel values, expressed with
    standard medical abbreviations (HR, BP, SpO2, RR, MAP, Tmax, etc.).
  - Assessment (A): one-line clinical impression; simulated stability status.
  - Plan (P): monitoring / no-action statement appropriate to simulated data.

ABBREVIATION GUIDANCE
  - HR = heart rate (beats/min)
  - BP = blood pressure (mmHg, systolic/diastolic)
  - SpO2 = oxygen saturation (%)
  - RR = respiratory rate (/min)
  - MAP = mean arterial pressure (mmHg)
  - T = temperature
  - Use concise, clinician-style phrasing. Include brief subjective reasoning.

CONSTRAINTS
  - Do not invent clinical events not supported by the supplied telemetry.
  - State clearly when values are within expected simulated bounds.
  - Mark the note as SIMULATED where appropriate for test provenance.
