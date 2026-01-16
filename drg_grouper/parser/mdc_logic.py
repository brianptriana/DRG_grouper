"""Parser for MDC logic files - extracts procedure codes and decision logic."""

import re
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class ProcedureCodeInfo:
    """Information about a procedure code from MDC files."""
    code: str
    description: str
    is_or_procedure: bool  # True if operating room procedure
    drgs: list[str] = field(default_factory=list)
    requires_combination: bool = False  # True if needs another procedure
    combination_codes: list[str] = field(default_factory=list)


@dataclass
class DRGLogic:
    """Logic for a DRG group (MCC/CC to DRG mapping)."""
    drgs: list[str]  # e.g., ["001", "002"] for MCC/no-MCC split
    base_description: str
    mcc_drg: str | None = None  # DRG with MCC
    cc_drg: str | None = None   # DRG with CC
    no_cc_drg: str | None = None  # DRG without CC/MCC
    procedures: list[str] = field(default_factory=list)  # Procedure codes


def parse_mdc_file(filepath: Path) -> tuple[dict[str, ProcedureCodeInfo], dict[str, DRGLogic]]:
    """
    Parse an MDC logic file to extract procedure codes and DRG logic.

    Returns:
        - procedure_codes: Dict mapping procedure code to ProcedureCodeInfo
        - drg_logic: Dict mapping DRG to DRGLogic
    """
    procedure_codes = {}
    drg_logic = {}

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    lines = content.split('\n')

    current_drg = None
    current_section = None  # "OR", "NON-OR", "DIAGNOSIS"
    is_or_section = False
    pending_combination = None

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Detect DRG definition lines
        drg_match = re.match(r'^DRG\s+(\d{3})\s+(.+)$', stripped)
        if drg_match:
            current_drg = drg_match.group(1)
            description = drg_match.group(2)

            # Try to determine MCC/CC/None from description
            if current_drg not in drg_logic:
                drg_logic[current_drg] = DRGLogic(
                    drgs=[current_drg],
                    base_description=description
                )

            # Detect severity level from description
            if 'with MCC' in description:
                # This is the MCC variant - find base DRG group
                base_drg = current_drg
                drg_logic[current_drg].mcc_drg = current_drg
            elif 'with CC' in description and 'without CC' not in description:
                drg_logic[current_drg].cc_drg = current_drg
            elif 'without CC/MCC' in description or 'without MCC' in description:
                drg_logic[current_drg].no_cc_drg = current_drg

            continue

        # Detect section headers
        if 'OPERATING ROOM PROCEDURES' in stripped and 'NON-' not in stripped:
            current_section = "OR"
            is_or_section = True
            continue
        elif 'NON-OPERATING ROOM PROCEDURES' in stripped:
            current_section = "NON-OR"
            is_or_section = False
            continue
        elif 'PRINCIPAL' in stripped or 'SECONDARY' in stripped:
            current_section = "DIAGNOSIS"
            continue

        # Skip non-procedure sections
        if current_section == "DIAGNOSIS":
            continue

        # Parse procedure codes
        # Format: "  02YA0Z0       Description..." or "   and 02RL0JZ  Description..."
        if current_section in ["OR", "NON-OR"]:
            # Check for "and" combination
            and_match = re.match(r'^\s+and\s+([A-Z0-9]{7})\*?\s+(.*)$', line)
            if and_match:
                code = and_match.group(1)
                desc = and_match.group(2).strip()

                if pending_combination and code:
                    # This is the second code in a combination
                    if pending_combination in procedure_codes:
                        procedure_codes[pending_combination].requires_combination = True
                        procedure_codes[pending_combination].combination_codes.append(code)

                    procedure_codes[code] = ProcedureCodeInfo(
                        code=code,
                        description=desc,
                        is_or_procedure=is_or_section,
                        drgs=[current_drg] if current_drg else []
                    )
                continue

            # Regular procedure code line
            proc_match = re.match(r'^\s{2}([A-Z0-9]{7})\*?\s+(.*)$', line)
            if proc_match:
                code = proc_match.group(1)
                desc = proc_match.group(2).strip()
                has_asterisk = '*' in line[:20]

                # Asterisk typically indicates non-OR or special handling
                effective_is_or = is_or_section and not has_asterisk

                if code not in procedure_codes:
                    procedure_codes[code] = ProcedureCodeInfo(
                        code=code,
                        description=desc,
                        is_or_procedure=effective_is_or,
                        drgs=[]
                    )

                if current_drg:
                    procedure_codes[code].drgs.append(current_drg)

                # Check if next line is "and" for combination
                pending_combination = code

    return procedure_codes, drg_logic


def load_mdc_logic(data_dir: Path) -> tuple[dict[str, ProcedureCodeInfo], dict[str, DRGLogic]]:
    """Load all MDC logic from the definitions manual directory."""
    all_procedures = {}
    all_drg_logic = {}

    mdc_files = [
        "mdcs_00_07.txt",
        "mdcs_08_11.txt",
        "mdcs_12_21.txt",
        "mdcs_22_25.txt"
    ]

    for mdc_file in mdc_files:
        filepath = data_dir / mdc_file
        if filepath.exists():
            procedures, drg_logic = parse_mdc_file(filepath)
            all_procedures.update(procedures)
            all_drg_logic.update(drg_logic)

    return all_procedures, all_drg_logic


def get_drg_for_procedure(
    procedure_code: str,
    has_mcc: bool,
    has_cc: bool,
    procedures_dict: dict[str, ProcedureCodeInfo],
    drg_logic_dict: dict[str, DRGLogic]
) -> str | None:
    """
    Get the DRG for a procedure code based on CC/MCC status.
    Returns the DRG number or None if not found.
    """
    code = procedure_code.upper().replace(".", "")
    proc_info = procedures_dict.get(code)

    if not proc_info or not proc_info.drgs:
        return None

    # Get the first associated DRG and find the right severity variant
    base_drg = proc_info.drgs[0]
    logic = drg_logic_dict.get(base_drg)

    if not logic:
        return base_drg

    if has_mcc and logic.mcc_drg:
        return logic.mcc_drg
    elif has_cc and logic.cc_drg:
        return logic.cc_drg
    elif logic.no_cc_drg:
        return logic.no_cc_drg

    return base_drg
