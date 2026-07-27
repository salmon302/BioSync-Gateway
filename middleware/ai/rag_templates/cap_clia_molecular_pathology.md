# SPDX-License-Identifier: MIT
# CAP/CLIA Molecular Pathology Summary Report Template
#
# Static RAG template (FR-3.15.3 / C9). Used by the ClinVar -> Molecular
# Pathology Summary Report endpoint (FR-3.15.5). The LLM is instructed to
# merge structured ClinVar variant data into this CAP/CLIA-shaped skeleton.
# This is a SIMULATION template for LIMS/EHR text-ingestion testing only and
# must not be used for real patient care.

# TEMPLATE TYPE: cap_clia
# DESCRIPTION: CAP/CLIA molecular pathology summary report skeleton

MOLECULAR PATHOLOGY SUMMARY REPORT
==================================

1. SPECIMEN INFORMATION
   - Specimen type: _________________________________
   - Collection date: _________________________________
   - Received date: _________________________________
   - Ordering provider: _________________________________

2. ASSAY / METHODOLOGY
   - Test ordered: Germline/Somatic variant panel
   - Platform: NGS (simulated)
   - Validation status: CAP/CLIA validated (simulated)

3. VARIANT FINDINGS
   - Gene: _________________________________
   - Transcript / HGVS: _________________________________
   - Nucleotide change: _________________________________
   - Protein change: _________________________________
   - Genomic coordinates (GRCh38): _________________________________
   - Clinical significance (per ClinVar): _________________________________
   - Review status: _________________________________

4. INTERPRETATION
   - Pathogenic/Likely pathogenic variants are reported with their established
     cancer association and penetrance where known.
   - Variants of uncertain significance (VUS) are summarized without clinical
     actionability claims.

5. RECOMMENDATIONS
   - Correlate with tumor phenotype and family history.
   - Consider genetic counseling referral where guidelines indicate.
   - Recommend cascade testing of at-risk relatives where appropriate.

6. DISCLAIMER
   This is a SIMULATED report generated for LIMS/EHR ingestion and validation
   testing (FR-3.15.5). It contains no real patient data and must not be used
   for clinical decision-making.
