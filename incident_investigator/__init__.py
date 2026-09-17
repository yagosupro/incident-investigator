"""A zero-dependency, evidence-first incident investigation demonstration."""

from .backend import SimulatedBackend
from .investigator import InvestigationReport, Investigator

__all__ = ["Investigator", "InvestigationReport", "SimulatedBackend"]
