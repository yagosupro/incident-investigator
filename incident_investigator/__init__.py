"""A zero-dependency, evidence-first incident investigation demonstration."""

from .backend import SimulatedBackend
from .investigator import InvestigationReport, Investigator
from .model_loop import ModelInvestigationLoop, ModelInvestigationReport, ScriptedOfflineAdapter
from .ollama import OllamaLocalAdapter

__all__ = [
    "Investigator", "InvestigationReport", "ModelInvestigationLoop", "ModelInvestigationReport",
    "OllamaLocalAdapter", "ScriptedOfflineAdapter", "SimulatedBackend",
]
