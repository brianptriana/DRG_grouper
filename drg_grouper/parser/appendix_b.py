"""Parser for Appendix B - Diagnosis Code/MDC/MS-DRG Index."""

import re
from pathlib import Path
from ..data.models import DiagnosisInfo


def parse_appendix_b(filepath: Path) -> dict[str, DiagnosisInfo]:
    """
    Parse Appendix B to extract diagnosis code to MDC/DRG mappings.

    Format:
    I10 Dx  MDC DRG(s)      ICD-10-CM Description
    A000    06  371-373     Cholera due to Vibrio cholerae 01, biovar cholerae
    A021    18  870-872     Salmonella sepsis
            25  974-976     (continuation line - same diagnosis, different MDC)

    Returns a dictionary mapping diagnosis code to DiagnosisInfo.
    """
    diagnoses = {}
    current_dx = None
    current_mappings = []
    current_description = ""

    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    in_data = False

    for line in lines:
        # Skip header
        if 'I10 Dx' in line and 'MDC' in line:
            in_data = True
            continue

        if not in_data:
            continue

        if not line.strip():
            continue

        # Check if this is a new diagnosis or continuation
        # New diagnosis: starts with a letter/digit in position 1
        # Continuation: starts with spaces, then MDC

        dx_code = line[0:8].strip()

        if dx_code:  # New diagnosis
            # Save previous diagnosis if exists
            if current_dx and current_mappings:
                diagnoses[current_dx] = DiagnosisInfo(
                    code=current_dx,
                    description=current_description,
                    mdc_drg_mappings=current_mappings
                )

            current_dx = dx_code
            current_mappings = []

            # Parse MDC and DRGs
            mdc = line[8:12].strip()
            drg_range = line[12:24].strip()
            description = line[24:].strip()
            current_description = description

            if mdc and drg_range:
                drgs = expand_drg_range(drg_range)
                current_mappings.append((mdc, drgs))

        else:  # Continuation line
            # Parse MDC and DRGs from continuation
            mdc = line[8:12].strip()
            drg_range = line[12:24].strip()

            if mdc and drg_range:
                drgs = expand_drg_range(drg_range)
                current_mappings.append((mdc, drgs))

    # Don't forget the last diagnosis
    if current_dx and current_mappings:
        diagnoses[current_dx] = DiagnosisInfo(
            code=current_dx,
            description=current_description,
            mdc_drg_mappings=current_mappings
        )

    return diagnoses


def expand_drg_range(drg_range: str) -> list[str]:
    """
    Expand a DRG range like '371-373' into ['371', '372', '373'].
    Also handles comma-separated values like '371,373'.
    """
    drgs = []

    # Handle comma-separated ranges
    parts = drg_range.replace(' ', '').split(',')

    for part in parts:
        if '-' in part:
            # Range like 371-373
            start, end = part.split('-', 1)
            try:
                start_num = int(start)
                end_num = int(end)
                for i in range(start_num, end_num + 1):
                    drgs.append(str(i).zfill(3))
            except ValueError:
                drgs.append(part)
        else:
            # Single DRG
            try:
                drgs.append(str(int(part)).zfill(3))
            except ValueError:
                if part:
                    drgs.append(part)

    return drgs


def get_mdc_for_diagnosis(diagnosis_code: str, diagnoses: dict[str, DiagnosisInfo]) -> str | None:
    """
    Get the primary MDC for a diagnosis code.
    Returns the first MDC mapping (which is typically the primary assignment).
    """
    dx_info = diagnoses.get(diagnosis_code.upper().replace(".", ""))
    if dx_info and dx_info.mdc_drg_mappings:
        return dx_info.mdc_drg_mappings[0][0]
    return None


def load_diagnosis_mappings(data_dir: Path) -> dict[str, DiagnosisInfo]:
    """Load diagnosis mappings from the definitions manual directory."""
    appendix_b_path = data_dir / "appendix_B.txt"
    if not appendix_b_path.exists():
        raise FileNotFoundError(f"Appendix B not found at {appendix_b_path}")
    return parse_appendix_b(appendix_b_path)
