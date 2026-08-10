"""Crowd-domain values fixed by the Epic 1 V3 handoff."""

from enum import Enum


class CrowdLevel(str, Enum):
    VERY_LOW = "VERY_LOW"
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    VERY_HIGH = "VERY_HIGH"


class FrontendCrowdLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class CrowdPreference(str, Enum):
    AVOID_BUSY = "AVOID_BUSY"
    PREFER_QUIETER = "PREFER_QUIETER"
    FLEXIBLE = "FLEXIBLE"


class CoverageStatus(str, Enum):
    SUPPORTED = "SUPPORTED"
    LIMITED = "LIMITED"
    NO_DATA = "NO_DATA"


class DataState(str, Enum):
    OK = "OK"
    AMBIGUOUS_NO_RECORD = "AMBIGUOUS_NO_RECORD"
    STALE = "STALE"
    CONFLICTED = "CONFLICTED"
    NO_DATA = "NO_DATA"
