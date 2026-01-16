"""Data models for the MS-DRG grouper."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class DRGType(Enum):
    """Type of DRG - Medical or Surgical."""
    MEDICAL = "M"
    SURGICAL = "P"


class CCLevel(Enum):
    """Complication/Comorbidity severity level."""
    NONE = "None"
    CC = "CC"
    MCC = "MCC"


class DischargeStatus(Enum):
    """Patient discharge status."""
    ALIVE = "alive"
    EXPIRED = "expired"
    TRANSFERRED = "transferred"


@dataclass
class Encounter:
    """Represents a patient encounter for DRG assignment."""
    principal_dx: str
    secondary_dx: list[str] = field(default_factory=list)
    procedures: list[str] = field(default_factory=list)
    age: int = 0
    sex: str = "U"  # M, F, or U (unknown)
    discharge_status: DischargeStatus = DischargeStatus.ALIVE

    def __post_init__(self):
        # Normalize codes - remove dots and uppercase
        self.principal_dx = self.principal_dx.replace(".", "").upper()
        self.secondary_dx = [dx.replace(".", "").upper() for dx in self.secondary_dx]
        self.procedures = [proc.replace(".", "").upper() for proc in self.procedures]
        self.sex = self.sex.upper()


@dataclass
class DRGDefinition:
    """Definition of a single MS-DRG."""
    drg: str
    mdc: Optional[str]  # None for Pre-MDC DRGs
    drg_type: DRGType
    description: str

    @property
    def is_surgical(self) -> bool:
        return self.drg_type == DRGType.SURGICAL


@dataclass
class DiagnosisInfo:
    """Information about a diagnosis code from Appendix B."""
    code: str
    description: str
    mdc_drg_mappings: list[tuple[str, list[str]]]  # List of (MDC, [DRGs])


@dataclass
class CCMCCInfo:
    """CC/MCC information for a diagnosis code from Appendix C."""
    code: str
    level: CCLevel
    pdx_exclusion_group: Optional[str]  # Reference to exclusion group
    description: str


@dataclass
class ProcedureInfo:
    """Information about a procedure code."""
    code: str
    description: str
    is_or_procedure: bool  # Operating room procedure
    drgs: list[str]  # DRGs this procedure is associated with


@dataclass
class DRGResult:
    """Result of DRG grouping."""
    drg: str
    mdc: Optional[str]
    description: str
    drg_type: DRGType
    mcc_dx: Optional[str] = None  # Diagnosis that triggered MCC
    cc_dx: Optional[str] = None   # Diagnosis that triggered CC
    surgical_procedure: Optional[str] = None  # Primary surgical procedure
    grouping_notes: list[str] = field(default_factory=list)

    @property
    def severity(self) -> CCLevel:
        if self.mcc_dx:
            return CCLevel.MCC
        elif self.cc_dx:
            return CCLevel.CC
        return CCLevel.NONE
