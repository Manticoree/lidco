"""Smart Error Recovery — classify, strategize, heal, learn."""
from __future__ import annotations

from lidco.recovery.classifier import ErrorClassification, ErrorClassifier
from lidco.recovery.learner import ErrorPatternLearner, Resolution
from lidco.recovery.self_heal import HealResult, SelfHealEngine
from lidco.recovery.strategy import RecoveryAction, RecoveryChain, RecoveryStrategy

__all__ = [
    "ErrorClassification",
    "ErrorClassifier",
    "ErrorPatternLearner",
    "HealResult",
    "RecoveryAction",
    "RecoveryChain",
    "RecoveryStrategy",
    "Resolution",
    "SelfHealEngine",
]
