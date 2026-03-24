"""Pipelines package — end-to-end automation workflows."""
from .issue_to_pr import IssueToPRPipeline, PipelineConfig, PipelineResult

__all__ = ["IssueToPRPipeline", "PipelineConfig", "PipelineResult"]
