"""Tests for the MS-DRG Grouper."""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from drg_grouper.data.models import Encounter, DischargeStatus
from drg_grouper.grouper import create_grouper


def test_basic_grouping():
    """Test basic grouper initialization and a simple case."""
    data_dir = Path(__file__).parent.parent / "msdrgv43.0icd10_r0_definitionsmanual_text"

    if not data_dir.exists():
        print(f"Data directory not found: {data_dir}")
        print("Please ensure the CMS definitions manual files are present.")
        return False

    print("Creating grouper...")
    grouper = create_grouper(data_dir)

    # Test case: Simple medical case - Atherosclerosis
    print("\nTest 1: Simple medical case - Atherosclerosis")
    encounter = Encounter(
        principal_dx="I2510",  # Atherosclerotic heart disease of native coronary artery
        secondary_dx=["E119", "I10"],  # Type 2 diabetes, Essential hypertension
        procedures=[],
        age=65,
        sex="M",
        discharge_status=DischargeStatus.ALIVE
    )

    result = grouper.group(encounter)
    print(f"  PDX: I2510 (Atherosclerotic heart disease)")
    print(f"  SDX: E119 (Diabetes), I10 (Hypertension)")
    print(f"  Result: DRG {result.drg} - {result.description}")
    print(f"  MDC: {result.mdc}")
    print(f"  Type: {'Surgical' if result.drg_type.value == 'P' else 'Medical'}")

    # Test case: Pneumonia with MCC
    print("\nTest 2: Medical case with MCC - Pneumonia")
    encounter2 = Encounter(
        principal_dx="J189",  # Pneumonia, unspecified organism
        secondary_dx=["E1100"],  # Type 2 diabetes with hyperosmolarity (MCC)
        procedures=[],
        age=70,
        sex="F",
        discharge_status=DischargeStatus.ALIVE
    )

    result2 = grouper.group(encounter2)
    print(f"  PDX: J189 (Pneumonia)")
    print(f"  SDX: E1100 (Diabetes with hyperosmolarity - MCC)")
    print(f"  Result: DRG {result2.drg} - {result2.description}")
    print(f"  MDC: {result2.mdc}")
    print(f"  MCC: {result2.mcc_dx or 'None'}")

    # Test case: Heart Transplant (Pre-MDC)
    print("\nTest 3: Pre-MDC case - Heart Transplant")
    encounter3 = Encounter(
        principal_dx="Z941",  # Heart transplant status
        secondary_dx=["I2510"],
        procedures=["02YA0Z0"],  # Heart transplant, allogeneic
        age=55,
        sex="M",
        discharge_status=DischargeStatus.ALIVE
    )

    result3 = grouper.group(encounter3)
    print(f"  PDX: Z941 (Heart transplant status)")
    print(f"  Procedure: 02YA0Z0 (Heart transplant)")
    print(f"  Result: DRG {result3.drg} - {result3.description}")
    print(f"  MDC: {result3.mdc or 'Pre-MDC'}")

    print("\nAll tests completed!")
    return True


if __name__ == "__main__":
    success = test_basic_grouping()
    sys.exit(0 if success else 1)
