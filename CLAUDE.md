# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MS-DRG Grouper - A Python implementation of the CMS MS-DRG (Medicare Severity Diagnosis Related Groups) v43.0 grouping logic. This tool assigns DRG codes to patient encounters based on diagnoses and procedures.

**Repository**: https://github.com/brianptriana/DRG_grouper

## Data Setup

The CMS definition files are not included in the repository. Download from CMS:
1. Visit: https://www.cms.gov/medicare/payment/prospective-payment-systems/acute-inpatient-pps/ms-drg-classifications-and-software
2. Download "ICD-10 MS-DRG Definitions Manual Text Files"
3. Extract to `msdrgv43.0icd10_r0_definitionsmanual_text/`

## Commands

### Run the grouper (single encounter)
```bash
python cli.py --data-dir msdrgv43.0icd10_r0_definitionsmanual_text \
              --pdx I2510 --sdx E119,I10 --proc 02703ZZ --age 65 --sex M -v
```

### Run tests
```bash
python tests/test_grouper.py
```

### Batch processing
```bash
python cli.py --data-dir msdrgv43.0icd10_r0_definitionsmanual_text \
              --input encounters.csv --output results.csv
```

## Architecture

```
drg_grouper/
├── parser/           # Parsers for CMS definition files
│   ├── appendix_a.py   # DRG list (770 DRGs)
│   ├── appendix_b.py   # Diagnosis → MDC/DRG mapping (67K codes)
│   ├── appendix_c.py   # CC/MCC definitions (18K codes)
│   └── mdc_logic.py    # Procedure codes and decision trees (62K codes)
├── data/
│   └── models.py     # Data classes (Encounter, DRGResult, CCLevel, etc.)
└── grouper.py        # Main grouping engine
```

### Grouping Algorithm Flow

1. Validate principal diagnosis exists in reference data
2. Determine MDC from principal diagnosis (Appendix B)
3. Check Pre-MDC conditions (transplants, ECMO, tracheostomy)
4. Find highest severity CC/MCC from secondary diagnoses (Appendix C)
5. If OR procedures present: follow surgical path with hierarchy
6. If no OR procedures: follow medical path based on principal diagnosis
7. Apply CC/MCC to select final DRG variant (MCC/CC/None)

### Key Data Files

The `msdrgv43.0icd10_r0_definitionsmanual_text/` directory should contain:
- `appendix_A.txt` - DRG definitions
- `appendix_B.txt` - Diagnosis codes to MDC/DRG mapping
- `appendix_C.txt` - CC/MCC levels and exclusions
- `mdcs_*.txt` - MDC logic with procedure codes and decision trees

## Known Limitations

1. **Multi-MDC diagnoses**: Some diagnoses (e.g., sepsis A419) map to multiple MDCs. Currently uses the first mapping; age-based MDC selection not implemented.
2. **Surgical hierarchy**: Basic implementation - may not correctly prioritize all procedures per CMS hierarchy.
3. **PDX exclusions**: CC/MCC exclusions based on principal diagnosis are tracked but not fully implemented.
4. **Combination procedures**: Some DRGs require specific procedure combinations; basic support only.

## Input Format

### Single encounter (CLI)
- `--pdx`: Principal diagnosis (ICD-10-CM, e.g., I2510)
- `--sdx`: Secondary diagnoses (comma-separated)
- `--proc`: Procedures (comma-separated ICD-10-PCS codes)
- `--age`: Patient age in years
- `--sex`: M/F/U
- `--discharge`: alive/expired/transferred

### Batch CSV format
```csv
encounter_id,principal_dx,secondary_dx,procedures,age,sex,discharge_status
001,I2510,E119;I10,,65,M,alive
002,J189,E1100,02703ZZ,70,F,alive
```
Note: Use semicolons to separate multiple diagnoses/procedures in CSV.
