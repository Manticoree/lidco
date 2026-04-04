"""
GitLab CI/CD pipeline monitor (simulated).

List pipelines, inspect jobs, retrieve logs, retry failed jobs, download artifacts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Job:
    """Represents a CI/CD job."""

    id: int
    name: str
    status: str = "pending"
    log: str = ""
    artifact_path: str = ""


@dataclass
class Pipeline:
    """Represents a CI/CD pipeline."""

    id: int
    project_id: int
    ref: str = "main"
    status: str = "pending"
    jobs: list[Job] = field(default_factory=list)


class PipelineMonitor:
    """Simulated GitLab CI/CD pipeline monitor."""

    def __init__(self) -> None:
        self._pipelines: dict[int, Pipeline] = {}
        self._jobs: dict[int, Job] = {}
        self._next_pipeline_id = 1
        self._next_job_id = 1

    def list_pipelines(self, project_id: int) -> list[Pipeline]:
        """List pipelines for a project."""
        return [
            p for p in self._pipelines.values()
            if p.project_id == project_id
        ]

    def get_pipeline(self, pipeline_id: int) -> Pipeline:
        """Get a pipeline by ID."""
        if pipeline_id not in self._pipelines:
            raise KeyError(f"Pipeline {pipeline_id} not found")
        return self._pipelines[pipeline_id]

    def job_logs(self, job_id: int) -> str:
        """Retrieve log output for a job."""
        job = self._jobs.get(job_id)
        if job is None:
            raise KeyError(f"Job {job_id} not found")
        return job.log

    def retry_job(self, job_id: int) -> bool:
        """Retry a failed job. Returns True on success."""
        job = self._jobs.get(job_id)
        if job is None:
            raise KeyError(f"Job {job_id} not found")
        if job.status != "failed":
            raise ValueError(f"Can only retry failed jobs, got '{job.status}'")
        job.status = "pending"
        return True

    def download_artifact(self, job_id: int, path: str) -> bool:
        """Download artifact for a job to the given path (simulated)."""
        job = self._jobs.get(job_id)
        if job is None:
            raise KeyError(f"Job {job_id} not found")
        if not job.artifact_path:
            raise FileNotFoundError(f"No artifact for job {job_id}")
        if not path:
            raise ValueError("Download path must not be empty")
        return True

    # -- helpers for simulated state --

    def _add_pipeline(self, project_id: int, ref: str = "main", status: str = "pending") -> Pipeline:
        pid = self._next_pipeline_id
        self._next_pipeline_id += 1
        pipeline = Pipeline(id=pid, project_id=project_id, ref=ref, status=status)
        self._pipelines[pid] = pipeline
        return pipeline

    def _add_job(
        self,
        pipeline_id: int,
        name: str,
        status: str = "pending",
        log: str = "",
        artifact_path: str = "",
    ) -> Job:
        jid = self._next_job_id
        self._next_job_id += 1
        job = Job(id=jid, name=name, status=status, log=log, artifact_path=artifact_path)
        self._jobs[jid] = job
        pipeline = self._pipelines.get(pipeline_id)
        if pipeline is not None:
            pipeline.jobs.append(job)
        return job
