"""Parser for Appendix C - CC/MCC Definitions and Exclusions."""

import re
from pathlib import Path
from ..data.models import CCMCCInfo, CCLevel


def parse_appendix_c(filepath: Path) -> tuple[dict[str, CCMCCInfo], set[str], dict[str, set[str]]]:
    """
    Parse Appendix C to extract CC/MCC definitions.

    Format of Part 1:
    ' I10 Dx  Lev PDX Exclusions   ICD-10-CM Description'
    ' A000    CC  0002:3 codes     Cholera due to Vibrio cholerae 01, biovar cholerae'

    Returns:
        - cc_mcc_dict: Dict mapping diagnosis code to CCMCCInfo
        - discharge_alive_codes: Set of codes that are CC/MCC only if discharged alive
        - drg_exclusions: Dict mapping DRG to set of excluded diagnosis codes
    """
    cc_mcc_dict = {}
    discharge_alive_codes = set()
    drg_exclusions = {}  # DRG -> set of excluded codes
    current_drg_list = []

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    lines = content.split('\n')
    section = "header"  # Start before Part 1
    in_data = False

    for line in lines:
        stripped = line.strip()

        # Detect section changes
        if 'Part 1' in line and 'List of CC' in line:
            section = "part1"
            in_data = False
            continue
        elif 'Part 2' in line:
            section = "part2"
            in_data = False
            continue
        elif 'Part 3' in line:
            section = "part3"
            in_data = False
            current_drg_list = []
            continue

        # Skip headers and empty lines
        if not stripped or stripped.startswith(':') or stripped.startswith('|'):
            continue

        # Skip header line in each section
        if 'I10 Dx' in line and 'Lev' in line:
            in_data = True
            continue

        if section == "part1" and in_data:
            # Format: ' A000    CC  0002:3 codes     Cholera...'
            # The line starts with a space, then code
            # Columns: 1-8 code, 8-12 level (CC/MCC), 12+ exclusion and description
            if len(line) < 12:
                continue

            code = line[1:8].strip()
            if not code or not code[0].isalnum():
                continue

            level_str = line[8:12].strip()
            if level_str == "CC":
                level = CCLevel.CC
            elif level_str == "MCC":
                level = CCLevel.MCC
            else:
                continue

            # Extract exclusion group reference and description
            rest = line[12:].strip() if len(line) > 12 else ""
            exclusion_ref = ""
            description = rest

            # Try to extract the exclusion reference (format: "0002:3 codes")
            excl_match = re.match(r'^(\d+:\d+\s+codes?)\s+(.*)$', rest)
            if excl_match:
                exclusion_ref = excl_match.group(1)
                description = excl_match.group(2)

            cc_mcc_dict[code] = CCMCCInfo(
                code=code,
                level=level,
                pdx_exclusion_group=exclusion_ref if exclusion_ref else None,
                description=description
            )

        elif section == "part2":
            # These are codes that are CC/MCC only if patient discharged alive
            # Format: '  I462    Cardiac arrest due to underlying cardiac condition'
            code = stripped.split()[0] if stripped.split() else ""
            if code and code[0].isalnum() and len(code) <= 8:
                discharge_alive_codes.add(code)

        elif section == "part3":
            # DRG-specific exclusions
            # Format: 'MDC XX DRGs XXX-XXX Description'
            #         followed by list of excluded codes
            if 'MDC' in line and 'DRG' in line:
                # Extract DRG range
                drg_match = re.search(r'DRGs?\s+(\d+(?:-\d+)?)', line)
                if drg_match:
                    drg_range = drg_match.group(1)
                    current_drg_list = expand_drg_range_simple(drg_range)
                    for drg in current_drg_list:
                        if drg not in drg_exclusions:
                            drg_exclusions[drg] = set()
                continue

            # Excluded diagnosis codes
            code = stripped.split()[0] if stripped.split() else ""
            if code and code[0].isalnum() and len(code) <= 8 and current_drg_list:
                for drg in current_drg_list:
                    drg_exclusions[drg].add(code)

    return cc_mcc_dict, discharge_alive_codes, drg_exclusions


def expand_drg_range_simple(drg_range: str) -> list[str]:
    """Expand a DRG range like '082-084' into list of DRGs."""
    if '-' in drg_range:
        parts = drg_range.split('-')
        try:
            start = int(parts[0])
            end = int(parts[1])
            return [str(i).zfill(3) for i in range(start, end + 1)]
        except ValueError:
            return [drg_range]
    return [drg_range.zfill(3)]


def get_cc_level(diagnosis_code: str, cc_mcc_dict: dict[str, CCMCCInfo]) -> CCLevel:
    """Get the CC/MCC level for a diagnosis code."""
    code = diagnosis_code.upper().replace(".", "")
    info = cc_mcc_dict.get(code)
    return info.level if info else CCLevel.NONE


def load_cc_mcc_definitions(data_dir: Path) -> tuple[dict[str, CCMCCInfo], set[str], dict[str, set[str]]]:
    """Load CC/MCC definitions from the definitions manual directory."""
    appendix_c_path = data_dir / "appendix_C.txt"
    if not appendix_c_path.exists():
        raise FileNotFoundError(f"Appendix C not found at {appendix_c_path}")
    return parse_appendix_c(appendix_c_path)
