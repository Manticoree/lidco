"""Scheduler package — cron-based task runner."""
from .cron_runner import CronRunner, CronTask, CronRunResult

# Backward-compatible aliases
ScheduledTask = CronTask
RunResult = CronRunResult

__all__ = ["CronRunner", "CronTask", "CronRunResult", "ScheduledTask", "RunResult"]
