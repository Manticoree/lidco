"""Tests for PipelineMonitor (Q290)."""

import unittest

from lidco.gitlab.pipeline import PipelineMonitor, Pipeline, Job


class TestListPipelines(unittest.TestCase):
    def test_empty(self):
        mon = PipelineMonitor()
        self.assertEqual(mon.list_pipelines(1), [])

    def test_filter_by_project(self):
        mon = PipelineMonitor()
        mon._add_pipeline(project_id=1)
        mon._add_pipeline(project_id=2)
        mon._add_pipeline(project_id=1)
        self.assertEqual(len(mon.list_pipelines(1)), 2)
        self.assertEqual(len(mon.list_pipelines(2)), 1)


class TestGetPipeline(unittest.TestCase):
    def test_get_existing(self):
        mon = PipelineMonitor()
        p = mon._add_pipeline(project_id=1, ref="develop", status="success")
        result = mon.get_pipeline(p.id)
        self.assertEqual(result.ref, "develop")
        self.assertEqual(result.status, "success")

    def test_get_missing_raises(self):
        mon = PipelineMonitor()
        with self.assertRaises(KeyError):
            mon.get_pipeline(999)


class TestJobLogs(unittest.TestCase):
    def test_get_log(self):
        mon = PipelineMonitor()
        p = mon._add_pipeline(project_id=1)
        j = mon._add_job(p.id, "test", log="Running tests...\nOK")
        self.assertEqual(mon.job_logs(j.id), "Running tests...\nOK")

    def test_empty_log(self):
        mon = PipelineMonitor()
        p = mon._add_pipeline(project_id=1)
        j = mon._add_job(p.id, "build")
        self.assertEqual(mon.job_logs(j.id), "")

    def test_missing_job_raises(self):
        mon = PipelineMonitor()
        with self.assertRaises(KeyError):
            mon.job_logs(999)


class TestRetryJob(unittest.TestCase):
    def test_retry_failed_job(self):
        mon = PipelineMonitor()
        p = mon._add_pipeline(project_id=1)
        j = mon._add_job(p.id, "lint", status="failed")
        self.assertTrue(mon.retry_job(j.id))
        self.assertEqual(j.status, "pending")

    def test_retry_non_failed_raises(self):
        mon = PipelineMonitor()
        p = mon._add_pipeline(project_id=1)
        j = mon._add_job(p.id, "build", status="success")
        with self.assertRaises(ValueError):
            mon.retry_job(j.id)

    def test_retry_missing_raises(self):
        mon = PipelineMonitor()
        with self.assertRaises(KeyError):
            mon.retry_job(999)


class TestDownloadArtifact(unittest.TestCase):
    def test_download_success(self):
        mon = PipelineMonitor()
        p = mon._add_pipeline(project_id=1)
        j = mon._add_job(p.id, "build", artifact_path="build.zip")
        self.assertTrue(mon.download_artifact(j.id, "/tmp/out"))

    def test_no_artifact_raises(self):
        mon = PipelineMonitor()
        p = mon._add_pipeline(project_id=1)
        j = mon._add_job(p.id, "test")
        with self.assertRaises(FileNotFoundError):
            mon.download_artifact(j.id, "/tmp/out")

    def test_empty_path_raises(self):
        mon = PipelineMonitor()
        p = mon._add_pipeline(project_id=1)
        j = mon._add_job(p.id, "build", artifact_path="x.zip")
        with self.assertRaises(ValueError):
            mon.download_artifact(j.id, "")

    def test_missing_job_raises(self):
        mon = PipelineMonitor()
        with self.assertRaises(KeyError):
            mon.download_artifact(999, "/tmp")


class TestAddJob(unittest.TestCase):
    def test_job_added_to_pipeline(self):
        mon = PipelineMonitor()
        p = mon._add_pipeline(project_id=1)
        j = mon._add_job(p.id, "deploy")
        self.assertIn(j, p.jobs)
        self.assertEqual(j.name, "deploy")


if __name__ == "__main__":
    unittest.main()
