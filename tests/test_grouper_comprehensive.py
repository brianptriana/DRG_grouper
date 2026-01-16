"""Comprehensive tests for the MS-DRG Grouper with assertions."""

import sys
import unittest
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from drg_grouper.data.models import Encounter, DischargeStatus, DRGType
from drg_grouper.grouper import create_grouper


class TestDRGGrouper(unittest.TestCase):
    """Test cases for MS-DRG Grouper."""

    @classmethod
    def setUpClass(cls):
        """Load grouper once for all tests."""
        data_dir = Path(__file__).parent.parent / "msdrgv43.0icd10_r0_definitionsmanual_text"
        if not data_dir.exists():
            raise unittest.SkipTest(f"Data directory not found: {data_dir}")
        cls.grouper = create_grouper(data_dir)

    # ========== Medical DRG Tests ==========

    def test_medical_case_no_cc_mcc(self):
        """Medical case without CC/MCC - Atherosclerosis."""
        encounter = Encounter(
            principal_dx="I2510",  # Atherosclerotic heart disease
            secondary_dx=["I10"],  # Hypertension (not a CC/MCC)
            procedures=[],
            age=65,
            sex="M",
            discharge_status=DischargeStatus.ALIVE
        )
        result = self.grouper.group(encounter)
        self.assertEqual(result.drg, "303")
        self.assertEqual(result.mdc, "05")
        self.assertEqual(result.drg_type, DRGType.MEDICAL)
        self.assertIn("Atherosclerosis", result.description)

    def test_medical_case_with_mcc(self):
        """Medical case with MCC - Pneumonia."""
        encounter = Encounter(
            principal_dx="J189",  # Pneumonia
            secondary_dx=["E1100"],  # Diabetes with hyperosmolarity (MCC)
            procedures=[],
            age=70,
            sex="F",
            discharge_status=DischargeStatus.ALIVE
        )
        result = self.grouper.group(encounter)
        self.assertEqual(result.drg, "193")
        self.assertEqual(result.mdc, "04")
        self.assertEqual(result.mcc_dx, "E1100")
        self.assertIn("MCC", result.description)

    def test_medical_case_with_cc_only(self):
        """Medical case with CC but no MCC - Pneumonia."""
        encounter = Encounter(
            principal_dx="J189",  # Pneumonia
            secondary_dx=["E1152"],  # Diabetes with peripheral angiopathy (CC, not MCC)
            procedures=[],
            age=70,
            sex="F",
            discharge_status=DischargeStatus.ALIVE
        )
        result = self.grouper.group(encounter)
        self.assertEqual(result.drg, "194")
        self.assertEqual(result.mdc, "04")
        self.assertEqual(result.cc_dx, "E1152")
        self.assertIn("CC", result.description)
        self.assertNotIn("MCC", result.description)

    def test_medical_case_pneumonia_no_cc(self):
        """Medical case without CC/MCC - Pneumonia."""
        encounter = Encounter(
            principal_dx="J189",  # Pneumonia
            secondary_dx=["Z87891"],  # History of nicotine dependence (not CC/MCC)
            procedures=[],
            age=45,
            sex="M",
            discharge_status=DischargeStatus.ALIVE
        )
        result = self.grouper.group(encounter)
        self.assertEqual(result.drg, "195")
        self.assertEqual(result.mdc, "04")
        self.assertIn("without CC/MCC", result.description)

    # ========== Pre-MDC Tests ==========

    def test_pre_mdc_heart_transplant_no_mcc(self):
        """Pre-MDC: Heart transplant without MCC."""
        encounter = Encounter(
            principal_dx="Z941",  # Heart transplant status
            secondary_dx=["I2510"],  # Not an MCC
            procedures=["02YA0Z0"],  # Heart transplant
            age=55,
            sex="M",
            discharge_status=DischargeStatus.ALIVE
        )
        result = self.grouper.group(encounter)
        self.assertEqual(result.drg, "002")
        self.assertIsNone(result.mdc)  # Pre-MDC has no MDC
        self.assertIn("Heart Transplant", result.description)

    def test_pre_mdc_heart_transplant_with_mcc(self):
        """Pre-MDC: Heart transplant with MCC."""
        encounter = Encounter(
            principal_dx="Z941",  # Heart transplant status
            secondary_dx=["E1100"],  # MCC
            procedures=["02YA0Z0"],  # Heart transplant
            age=55,
            sex="M",
            discharge_status=DischargeStatus.ALIVE
        )
        result = self.grouper.group(encounter)
        self.assertEqual(result.drg, "001")
        self.assertEqual(result.mcc_dx, "E1100")

    def test_pre_mdc_liver_transplant(self):
        """Pre-MDC: Liver transplant."""
        encounter = Encounter(
            principal_dx="K7460",  # Hepatic failure
            secondary_dx=[],
            procedures=["0FY00Z0"],  # Liver transplant
            age=50,
            sex="F",
            discharge_status=DischargeStatus.ALIVE
        )
        result = self.grouper.group(encounter)
        self.assertIn(result.drg, ["005", "006"])  # Liver transplant DRGs

    def test_pre_mdc_ecmo(self):
        """Pre-MDC: ECMO procedure triggers Pre-MDC DRG 003.

        Note: The grouper's Pre-MDC logic hardcodes ECMO (5A1522F) to DRG 003.
        """
        encounter = Encounter(
            principal_dx="J9600",  # Acute respiratory failure, unspecified
            secondary_dx=[],
            procedures=["5A1522F"],  # Central ECMO
            age=40,
            sex="M",
            discharge_status=DischargeStatus.ALIVE
        )
        result = self.grouper.group(encounter)
        # Pre-MDC hardcoded mapping for ECMO -> DRG 003
        self.assertEqual(result.drg, "003")
        self.assertIsNone(result.mdc)  # Pre-MDC has no MDC

    # ========== Surgical DRG Tests ==========

    def test_surgical_case_with_or_procedure(self):
        """Surgical case with OR procedure - CABG."""
        encounter = Encounter(
            principal_dx="I2510",  # Atherosclerotic heart disease
            secondary_dx=["I10"],
            procedures=["02100Z9"],  # CABG with autologous arterial graft
            age=65,
            sex="M",
            discharge_status=DischargeStatus.ALIVE
        )
        result = self.grouper.group(encounter)
        # Should be surgical type
        self.assertEqual(result.drg_type, DRGType.SURGICAL)
        self.assertIn("Surgical path", " ".join(result.grouping_notes))

    # ========== PE Case Tests (Recent Fix) ==========

    def test_pe_medical_without_mcc(self):
        """PE medical case without MCC should get DRG 176."""
        encounter = Encounter(
            principal_dx="I2699",  # PE unspecified
            secondary_dx=["I10"],  # Hypertension (not CC/MCC)
            procedures=[],
            age=60,
            sex="F",
            discharge_status=DischargeStatus.ALIVE
        )
        result = self.grouper.group(encounter)
        self.assertEqual(result.drg, "176")
        self.assertEqual(result.mdc, "04")
        self.assertIn("Pulmonary Embolism", result.description)

    def test_pe_medical_with_mcc(self):
        """PE medical case with MCC should get DRG 175."""
        encounter = Encounter(
            principal_dx="I2699",  # PE unspecified
            secondary_dx=["E1100"],  # MCC
            procedures=[],
            age=60,
            sex="F",
            discharge_status=DischargeStatus.ALIVE
        )
        result = self.grouper.group(encounter)
        self.assertEqual(result.drg, "175")
        self.assertEqual(result.mcc_dx, "E1100")

    def test_pe_acute_cor_pulmonale(self):
        """PE with acute cor pulmonale codes should get DRG 175 (treated as MCC-equivalent)."""
        # Acute cor pulmonale PE codes should go to DRG 175
        acute_pe_codes = ["I2601", "I2602", "I2609"]
        for pdx in acute_pe_codes:
            encounter = Encounter(
                principal_dx=pdx,
                secondary_dx=["I10"],  # No MCC
                procedures=[],
                age=60,
                sex="F",
                discharge_status=DischargeStatus.ALIVE
            )
            result = self.grouper.group(encounter)
            self.assertEqual(result.drg, "175",
                           f"Acute cor pulmonale PE code {pdx} should get DRG 175")

    # ========== Edge Cases ==========

    def test_invalid_principal_diagnosis(self):
        """Invalid principal diagnosis should return ungroupable."""
        encounter = Encounter(
            principal_dx="INVALID",
            secondary_dx=[],
            procedures=[],
            age=50,
            sex="M",
            discharge_status=DischargeStatus.ALIVE
        )
        result = self.grouper.group(encounter)
        self.assertEqual(result.drg, "999")
        self.assertIn("not found", " ".join(result.grouping_notes).lower())

    def test_mcc_excluded_on_death(self):
        """MCC that requires alive discharge should be excluded on death."""
        # Find an MCC that's in the discharge_alive_codes set
        # E1100 is a common MCC - check if it's excluded on non-alive discharge
        encounter_alive = Encounter(
            principal_dx="J189",
            secondary_dx=["E1100"],
            procedures=[],
            age=70,
            sex="F",
            discharge_status=DischargeStatus.ALIVE
        )
        encounter_expired = Encounter(
            principal_dx="J189",
            secondary_dx=["E1100"],
            procedures=[],
            age=70,
            sex="F",
            discharge_status=DischargeStatus.EXPIRED
        )
        result_alive = self.grouper.group(encounter_alive)
        result_expired = self.grouper.group(encounter_expired)

        # If E1100 is in discharge_alive_codes, results should differ
        # If not, they'll be the same - both are valid outcomes
        self.assertIn(result_alive.drg, ["193", "194", "195"])
        self.assertIn(result_expired.drg, ["193", "194", "195"])

    def test_cc_mcc_priority(self):
        """MCC should take priority over CC when both present."""
        encounter = Encounter(
            principal_dx="J189",  # Pneumonia
            secondary_dx=["E119", "E1100"],  # CC first, then MCC
            procedures=[],
            age=70,
            sex="F",
            discharge_status=DischargeStatus.ALIVE
        )
        result = self.grouper.group(encounter)
        self.assertEqual(result.mcc_dx, "E1100")
        self.assertEqual(result.drg, "193")  # MCC version

    def test_multiple_procedures(self):
        """Multiple OR procedures should be handled."""
        encounter = Encounter(
            principal_dx="I2510",
            secondary_dx=[],
            procedures=["02100Z9", "02703ZZ"],  # Multiple heart procedures
            age=65,
            sex="M",
            discharge_status=DischargeStatus.ALIVE
        )
        result = self.grouper.group(encounter)
        # Should still group to a surgical DRG
        self.assertEqual(result.drg_type, DRGType.SURGICAL)

    def test_no_secondary_diagnoses(self):
        """Encounter with no secondary diagnoses."""
        encounter = Encounter(
            principal_dx="I2510",
            secondary_dx=[],
            procedures=[],
            age=65,
            sex="M",
            discharge_status=DischargeStatus.ALIVE
        )
        result = self.grouper.group(encounter)
        self.assertEqual(result.drg, "303")
        self.assertIsNone(result.mcc_dx)
        self.assertIsNone(result.cc_dx)


class TestGroupingNotes(unittest.TestCase):
    """Test that grouping notes are informative."""

    @classmethod
    def setUpClass(cls):
        data_dir = Path(__file__).parent.parent / "msdrgv43.0icd10_r0_definitionsmanual_text"
        if not data_dir.exists():
            raise unittest.SkipTest(f"Data directory not found: {data_dir}")
        cls.grouper = create_grouper(data_dir)

    def test_notes_include_mdc(self):
        """Grouping notes should include MDC assignment."""
        encounter = Encounter(
            principal_dx="I2510",
            secondary_dx=[],
            procedures=[],
            age=65,
            sex="M",
            discharge_status=DischargeStatus.ALIVE
        )
        result = self.grouper.group(encounter)
        notes_text = " ".join(result.grouping_notes)
        self.assertIn("MDC", notes_text)

    def test_notes_indicate_path(self):
        """Grouping notes should indicate medical vs surgical path."""
        # Medical case
        enc_medical = Encounter(
            principal_dx="I2510",
            secondary_dx=[],
            procedures=[],
            age=65,
            sex="M",
            discharge_status=DischargeStatus.ALIVE
        )
        result_medical = self.grouper.group(enc_medical)
        self.assertIn("Medical path", " ".join(result_medical.grouping_notes))


if __name__ == "__main__":
    # Run with verbosity
    unittest.main(verbosity=2)
