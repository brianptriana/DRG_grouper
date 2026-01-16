"""Parser for Appendix A - List of MS-DRGs."""

import re
from pathlib import Path
from ..data.models import DRGDefinition, DRGType


def parse_appendix_a(filepath: Path) -> dict[str, DRGDefinition]:
    """
    Parse Appendix A to extract DRG definitions.

    Returns a dictionary mapping DRG number to DRGDefinition.
    """
    drg_definitions = {}

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Skip header lines until we get to actual data
    lines = content.split('\n')
    in_data = False

    for line in lines:
        # Skip empty lines and header
        if not line.strip():
            continue
        if line.startswith(':') or line.startswith('|') or line.startswith('Appendix'):
            continue
        if 'DRG MDC MS Description' in line:
            in_data = True
            continue

        if not in_data:
            continue

        # Parse data lines
        # Format: DRG MDC MS Description
        # Example: "001     P  Heart Transplant..."
        # Example: "020 01  P  Intracranial..."

        # DRG is first 3 chars
        if len(line) < 10:
            continue

        drg_num = line[0:3].strip()
        if not drg_num.isdigit():
            continue

        # MDC is chars 4-5 (positions 4-6, 0-indexed 3-5)
        mdc = line[4:6].strip() if len(line) > 5 else ""
        mdc = mdc if mdc else None

        # Type is around position 8
        drg_type_char = line[7:8].strip() if len(line) > 8 else ""
        if drg_type_char == 'P':
            drg_type = DRGType.SURGICAL
        elif drg_type_char == 'M':
            drg_type = DRGType.MEDICAL
        else:
            # Try to find M or P in the line
            match = re.search(r'\s([MP])\s+', line[4:12])
            if match:
                drg_type = DRGType.SURGICAL if match.group(1) == 'P' else DRGType.MEDICAL
            else:
                continue

        # Description is everything after position 10
        description = line[10:].strip() if len(line) > 10 else ""

        drg_definitions[drg_num] = DRGDefinition(
            drg=drg_num,
            mdc=mdc,
            drg_type=drg_type,
            description=description
        )

    return drg_definitions


def load_drg_definitions(data_dir: Path) -> dict[str, DRGDefinition]:
    """Load DRG definitions from the definitions manual directory."""
    appendix_a_path = data_dir / "appendix_A.txt"
    if not appendix_a_path.exists():
        raise FileNotFoundError(f"Appendix A not found at {appendix_a_path}")
    return parse_appendix_a(appendix_a_path)
