"""Spec-driven development pipeline: NL → requirements → design → tasks."""
from lidco.spec.writer import SpecDocument, SpecWriter
from lidco.spec.design_doc import Component, DesignDocument, DesignDocGenerator
from lidco.spec.task_decomposer import SpecTask, TaskDecomposer
from lidco.spec.context import SpecContextProvider
from lidco.spec.drift_detector import DriftDetector, DriftReport

__all__ = [
    "SpecDocument",
    "SpecWriter",
    "Component",
    "DesignDocument",
    "DesignDocGenerator",
    "SpecTask",
    "TaskDecomposer",
    "SpecContextProvider",
    "DriftDetector",
    "DriftReport",
]
