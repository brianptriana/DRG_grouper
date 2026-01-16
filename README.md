# MS-DRG Grouper

A Python implementation of the CMS MS-DRG (Medicare Severity Diagnosis Related Groups) v43.0 grouping logic. This tool assigns DRG codes to patient encounters based on ICD-10 diagnoses and procedures.

## Features

- Parses official CMS MS-DRG definition files
- Assigns DRGs based on principal diagnosis, secondary diagnoses, and procedures
- Handles CC/MCC (Complication/Comorbidity and Major CC) severity levels
- Supports Pre-MDC conditions (transplants, ECMO, etc.)
- Command-line interface for single encounters and batch processing

## Installation

```bash
git clone https://github.com/YOUR_USERNAME/DRG_grouper.git
cd DRG_grouper
```

No external dependencies required - uses Python standard library only.

## Data Files Setup

This grouper requires the official CMS MS-DRG definition files, which are not included in this repository due to size and licensing.

1. Download the MS-DRG v43.0 Definitions Manual from CMS:
   - Visit: https://www.cms.gov/medicare/payment/prospective-payment-systems/acute-inpatient-pps/ms-drg-classifications-and-software
   - Download the "ICD-10 MS-DRG Definitions Manual Text Files"

2. Extract the files to a directory (e.g., `msdrgv43.0icd10_r0_definitionsmanual_text/`)

3. The directory should contain:
   - `appendix_A.txt` - DRG list
   - `appendix_B.txt` - Diagnosis code mappings
   - `appendix_C.txt` - CC/MCC definitions
   - `mdcs_00_07.txt`, `mdcs_08_11.txt`, etc. - MDC logic files

## Usage

### Single Encounter

```bash
python cli.py --data-dir /path/to/definitions \
              --pdx I2510 \
              --sdx E119,I10 \
              --age 65 \
              --sex M \
              -v
```

**Options:**
- `--pdx`: Principal diagnosis (ICD-10-CM code)
- `--sdx`: Secondary diagnoses (comma-separated)
- `--proc`: Procedure codes (comma-separated ICD-10-PCS codes)
- `--age`: Patient age in years
- `--sex`: M (Male), F (Female), or U (Unknown)
- `--discharge`: alive, expired, or transferred
- `-v, --verbose`: Show detailed grouping notes

### Batch Processing

```bash
python cli.py --data-dir /path/to/definitions \
              --input encounters.csv \
              --output results.csv
```

**Input CSV format:**
```csv
encounter_id,principal_dx,secondary_dx,procedures,age,sex,discharge_status
001,I2510,E119;I10,,65,M,alive
002,J189,E1100,02703ZZ,70,F,alive
```

Note: Use semicolons to separate multiple diagnoses/procedures within a field.

### Python API

```python
from drg_grouper.data.models import Encounter, DischargeStatus
from drg_grouper.grouper import create_grouper

# Initialize grouper
grouper = create_grouper("/path/to/definitions")

# Create encounter
encounter = Encounter(
    principal_dx="I2510",
    secondary_dx=["E119", "I10"],
    procedures=[],
    age=65,
    sex="M",
    discharge_status=DischargeStatus.ALIVE
)

# Get DRG
result = grouper.group(encounter)
print(f"DRG: {result.drg} - {result.description}")
```

## Example Output

```
============================================================
MS-DRG GROUPING RESULT
============================================================
DRG:         303
Description: Atherosclerosis without MCC
MDC:         05
Type:        Medical
CC/MCC:      None

Grouping Notes:
  - MDC 05 from PDX I2510
  - Medical path: no OR procedures
============================================================
```

## Limitations

- **Multi-MDC diagnoses**: Some diagnoses map to multiple MDCs (e.g., sepsis). Currently uses the first mapping; age-based selection not implemented.
- **Surgical hierarchy**: Basic implementation of procedure prioritization.
- **PDX exclusions**: CC/MCC exclusions based on principal diagnosis are tracked but not fully applied.

## License

MIT License - see LICENSE file.

Note: The CMS MS-DRG definition files are produced by CMS and have their own terms of use.
