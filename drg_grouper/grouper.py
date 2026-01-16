"""Main MS-DRG Grouper Engine."""

from pathlib import Path
from .data.models import (
    Encounter, DRGResult, DRGDefinition, DiagnosisInfo,
    CCMCCInfo, CCLevel, DRGType, DischargeStatus
)
from .parser.appendix_a import load_drg_definitions
from .parser.appendix_b import load_diagnosis_mappings, get_mdc_for_diagnosis
from .parser.appendix_c import load_cc_mcc_definitions, get_cc_level
from .parser.mdc_logic import load_mdc_logic, ProcedureCodeInfo, DRGLogic


class DRGGrouper:
    """MS-DRG Grouper - assigns DRGs to patient encounters."""

    def __init__(self, data_dir: str | Path):
        """
        Initialize the grouper with CMS definition files.

        Args:
            data_dir: Path to directory containing the definitions manual text files
        """
        self.data_dir = Path(data_dir)
        self._load_data()

    def _load_data(self):
        """Load all reference data from the definitions manual."""
        print("Loading DRG definitions (Appendix A)...")
        self.drg_definitions = load_drg_definitions(self.data_dir)

        print("Loading diagnosis mappings (Appendix B)...")
        self.diagnosis_mappings = load_diagnosis_mappings(self.data_dir)

        print("Loading CC/MCC definitions (Appendix C)...")
        self.cc_mcc_dict, self.discharge_alive_codes, self.drg_exclusions = \
            load_cc_mcc_definitions(self.data_dir)

        print("Loading MDC logic files...")
        self.procedure_codes, self.drg_logic = load_mdc_logic(self.data_dir)

        print(f"Loaded {len(self.drg_definitions)} DRGs, "
              f"{len(self.diagnosis_mappings)} diagnoses, "
              f"{len(self.cc_mcc_dict)} CC/MCC codes, "
              f"{len(self.procedure_codes)} procedure codes")

    def group(self, encounter: Encounter) -> DRGResult:
        """
        Assign an MS-DRG to a patient encounter.

        Args:
            encounter: Patient encounter with diagnoses and procedures

        Returns:
            DRGResult with assigned DRG and supporting information
        """
        notes = []

        # Step 1: Validate principal diagnosis
        pdx = encounter.principal_dx
        if pdx not in self.diagnosis_mappings:
            return DRGResult(
                drg="999",
                mdc=None,
                description="Ungroupable",
                drg_type=DRGType.MEDICAL,
                grouping_notes=[f"Principal diagnosis {pdx} not found"]
            )

        # Step 2: Get MDC from principal diagnosis
        mdc = get_mdc_for_diagnosis(pdx, self.diagnosis_mappings)
        notes.append(f"MDC {mdc} from PDX {pdx}")

        # Step 3: Find highest severity CC/MCC from secondary diagnoses
        mcc_dx, cc_dx = self._find_cc_mcc(encounter)

        # Adjust for discharge status (some codes only count if alive)
        if encounter.discharge_status != DischargeStatus.ALIVE:
            if mcc_dx and mcc_dx in self.discharge_alive_codes:
                notes.append(f"MCC {mcc_dx} excluded (patient not discharged alive)")
                mcc_dx = None
            if cc_dx and cc_dx in self.discharge_alive_codes:
                notes.append(f"CC {cc_dx} excluded (patient not discharged alive)")
                cc_dx = None

        # Step 4: Check for Pre-MDC conditions (transplants, ECMO, etc.)
        pre_mdc_drg = self._check_pre_mdc(encounter, mcc_dx is not None)
        if pre_mdc_drg:
            drg_def = self.drg_definitions.get(pre_mdc_drg)
            return DRGResult(
                drg=pre_mdc_drg,
                mdc=None,
                description=drg_def.description if drg_def else "Pre-MDC",
                drg_type=drg_def.drg_type if drg_def else DRGType.SURGICAL,
                mcc_dx=mcc_dx,
                cc_dx=cc_dx if not mcc_dx else None,
                grouping_notes=notes + ["Assigned via Pre-MDC logic"]
            )

        # Step 5: Check for surgical procedures (OR procedures)
        or_procedures = self._find_or_procedures(encounter)

        if or_procedures:
            # Surgical path
            notes.append(f"Surgical path: {len(or_procedures)} OR procedure(s)")
            drg = self._assign_surgical_drg(
                mdc, or_procedures, mcc_dx is not None, cc_dx is not None
            )
        else:
            # Medical path
            notes.append("Medical path: no OR procedures")
            drg = self._assign_medical_drg(
                pdx, mdc, mcc_dx is not None, cc_dx is not None
            )

        if drg:
            drg_def = self.drg_definitions.get(drg)
            return DRGResult(
                drg=drg,
                mdc=mdc,
                description=drg_def.description if drg_def else "Unknown",
                drg_type=drg_def.drg_type if drg_def else DRGType.MEDICAL,
                mcc_dx=mcc_dx,
                cc_dx=cc_dx if not mcc_dx else None,
                surgical_procedure=or_procedures[0] if or_procedures else None,
                grouping_notes=notes
            )

        # Fallback - couldn't determine DRG
        return DRGResult(
            drg="999",
            mdc=mdc,
            description="Ungroupable",
            drg_type=DRGType.MEDICAL,
            grouping_notes=notes + ["Could not determine DRG"]
        )

    def _find_cc_mcc(self, encounter: Encounter) -> tuple[str | None, str | None]:
        """
        Find the highest severity CC/MCC from secondary diagnoses.
        Returns (mcc_dx, cc_dx) - the diagnoses that triggered each level.
        """
        mcc_dx = None
        cc_dx = None

        for dx in encounter.secondary_dx:
            dx_code = dx.upper().replace(".", "")
            cc_info = self.cc_mcc_dict.get(dx_code)

            if cc_info:
                if cc_info.level == CCLevel.MCC and not mcc_dx:
                    mcc_dx = dx_code
                elif cc_info.level == CCLevel.CC and not cc_dx:
                    cc_dx = dx_code

            # Stop if we found MCC (highest severity)
            if mcc_dx:
                break

        return mcc_dx, cc_dx

    def _find_or_procedures(self, encounter: Encounter) -> list[str]:
        """Find operating room procedures in the encounter."""
        or_procs = []

        for proc in encounter.procedures:
            proc_code = proc.upper().replace(".", "")
            proc_info = self.procedure_codes.get(proc_code)

            if proc_info and proc_info.is_or_procedure:
                or_procs.append(proc_code)

        return or_procs

    def _check_pre_mdc(self, encounter: Encounter, has_mcc: bool) -> str | None:
        """
        Check for Pre-MDC conditions that override normal MDC assignment.
        Returns DRG if Pre-MDC applies, None otherwise.
        """
        # Pre-MDC procedure codes (simplified - key transplant/ECMO codes)
        pre_mdc_procedures = {
            # Heart transplant
            "02YA0Z0": ("001", "002"),  # with MCC, without MCC
            "02YA0Z1": ("001", "002"),
            "02YA0Z2": ("001", "002"),
            # Liver transplant
            "0FY00Z0": ("005", "006"),
            "0FY00Z1": ("005", "006"),
            "0FY00Z2": ("005", "006"),
            # Lung transplant
            "0BYK0Z0": ("007", "007"),
            "0BYK0Z1": ("007", "007"),
            "0BYK0Z2": ("007", "007"),
            "0BYL0Z0": ("007", "007"),
            "0BYL0Z1": ("007", "007"),
            "0BYL0Z2": ("007", "007"),
            "0BYM0Z0": ("007", "007"),
            "0BYM0Z1": ("007", "007"),
            "0BYM0Z2": ("007", "007"),
            # ECMO
            "5A1522F": ("003", "003"),  # Central ECMO
        }

        for proc in encounter.procedures:
            proc_code = proc.upper().replace(".", "")
            if proc_code in pre_mdc_procedures:
                mcc_drg, no_mcc_drg = pre_mdc_procedures[proc_code]
                return mcc_drg if has_mcc else no_mcc_drg

        return None

    def _assign_surgical_drg(
        self,
        mdc: str,
        or_procedures: list[str],
        has_mcc: bool,
        has_cc: bool
    ) -> str | None:
        """Assign surgical DRG based on MDC and procedures."""
        # Find DRGs associated with the procedures
        for proc in or_procedures:
            proc_info = self.procedure_codes.get(proc)
            if proc_info and proc_info.drgs:
                # Get the base DRG and find severity variant
                base_drg = proc_info.drgs[0]
                base_def = self.drg_definitions.get(base_drg)

                if not base_def:
                    continue

                # Check if this DRG has severity variants by looking at description
                # DRGs with variants have "with MCC", "with CC", "without CC/MCC" in name
                base_desc = base_def.description.lower()
                has_severity_variants = (
                    'with mcc' in base_desc or
                    'without mcc' in base_desc or
                    'without cc' in base_desc
                )

                # If no severity variants in description, return base DRG as-is
                if not has_severity_variants:
                    return base_drg

                drg_num = int(base_drg)

                # Common pattern: DRGs come in triplets (MCC, CC, no CC)
                # Try to find the right severity variant
                if has_mcc:
                    # MCC is usually the first in a group
                    return base_drg
                elif has_cc:
                    # CC is usually +1
                    cc_drg = str(drg_num + 1).zfill(3)
                    cc_def = self.drg_definitions.get(cc_drg)
                    # Verify it's a CC variant (has "with CC" in description)
                    if cc_def and 'with cc' in cc_def.description.lower():
                        return cc_drg
                    return base_drg
                else:
                    # No CC/MCC is usually +2
                    no_cc_drg = str(drg_num + 2).zfill(3)
                    no_cc_def = self.drg_definitions.get(no_cc_drg)
                    # Verify it's a no-CC variant
                    if no_cc_def and 'without cc' in no_cc_def.description.lower():
                        return no_cc_drg
                    # Try +1 if +2 doesn't exist or isn't a variant
                    cc_drg = str(drg_num + 1).zfill(3)
                    cc_def = self.drg_definitions.get(cc_drg)
                    if cc_def and ('without' in cc_def.description.lower() or 'with cc' in cc_def.description.lower()):
                        return cc_drg
                    return base_drg

        return None

    # Surgical DRGs that require procedures - map to medical alternatives
    # Format: surgical_drg -> (mcc_drg, cc_drg, no_cc_drg) or (with_condition, without)
    SURGICAL_TO_MEDICAL_FALLBACK = {
        # DRG 173 (PE thrombolysis) -> DRGs 175/176 (PE medical)
        "173": ("175", "175", "176"),  # 175 for MCC/acute cor pulmonale, 176 without
    }

    def _assign_medical_drg(
        self,
        pdx: str,
        mdc: str,
        has_mcc: bool,
        has_cc: bool
    ) -> str | None:
        """Assign medical DRG based on principal diagnosis."""
        dx_info = self.diagnosis_mappings.get(pdx)
        if not dx_info:
            return None

        # Check for acute cor pulmonale in PE cases (counts as MCC equivalent)
        is_acute_cor_pulmonale = pdx in [
            "I2601", "I2602", "I2603", "I2604", "I2609"
        ]

        # Find DRGs for this MDC
        for mapping_mdc, drgs in dx_info.mdc_drg_mappings:
            if mapping_mdc == mdc and drgs:
                candidate_drg = drgs[0]

                # Check if this is a surgical DRG that needs a procedure
                drg_def = self.drg_definitions.get(candidate_drg)
                if drg_def and drg_def.is_surgical:
                    # Look for medical fallback
                    fallback = self.SURGICAL_TO_MEDICAL_FALLBACK.get(candidate_drg)
                    if fallback:
                        if has_mcc or is_acute_cor_pulmonale:
                            return fallback[0]
                        elif has_cc:
                            return fallback[1]
                        else:
                            return fallback[2]
                    # No fallback defined - skip this surgical DRG
                    continue

                # Medical DRGs often come in pairs or triplets
                if len(drgs) >= 3:
                    if has_mcc:
                        return drgs[0]
                    elif has_cc:
                        return drgs[1]
                    else:
                        return drgs[2]
                elif len(drgs) == 2:
                    if has_mcc or has_cc:
                        return drgs[0]
                    else:
                        return drgs[1]
                else:
                    return drgs[0]

        return None


def create_grouper(data_dir: str | Path) -> DRGGrouper:
    """Create a DRG grouper instance."""
    return DRGGrouper(data_dir)
