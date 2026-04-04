"""Tests for Q296 DockerfileGenerator."""
import unittest

from lidco.containers.dockerfile import DockerfileGenerator, Stage


class TestDockerfileGenerator(unittest.TestCase):
    def setUp(self):
        self.gen = DockerfileGenerator()

    # -- generate ----------------------------------------------------------

    def test_generate_python_basic(self):
        result = self.gen.generate("python")
        self.assertIn("FROM python:3.12-slim", result)
        self.assertIn("WORKDIR /app", result)
        self.assertIn("COPY . .", result)

    def test_generate_node_basic(self):
        result = self.gen.generate("node")
        self.assertIn("FROM node:20-alpine", result)

    def test_generate_unsupported_language_raises(self):
        with self.assertRaises(ValueError):
            self.gen.generate("cobol")

    def test_generate_with_framework_flask(self):
        result = self.gen.generate("python", "flask")
        self.assertIn("pip install", result)
        self.assertIn("flask", result.lower())
        self.assertIn("EXPOSE 5000", result)

    def test_generate_with_framework_express(self):
        result = self.gen.generate("node", "express")
        self.assertIn("npm ci", result)
        self.assertIn("EXPOSE 3000", result)

    def test_generate_with_unknown_framework_fallback(self):
        result = self.gen.generate("python", "unknown_fw")
        self.assertIn("COPY . .", result)
        self.assertNotIn("pip install", result)

    def test_generate_case_insensitive_language(self):
        result = self.gen.generate("Python")
        self.assertIn("FROM python:3.12-slim", result)

    def test_generate_fastapi(self):
        result = self.gen.generate("python", "fastapi")
        self.assertIn("uvicorn", result)
        self.assertIn("EXPOSE 8000", result)

    # -- multi_stage -------------------------------------------------------

    def test_multi_stage_single(self):
        stages = [Stage(name="build", base_image="golang:1.22", instructions=["COPY . .", "RUN go build -o /app"])]
        result = self.gen.multi_stage(stages)
        self.assertIn("FROM golang:1.22 AS build", result)
        self.assertIn("RUN go build -o /app", result)

    def test_multi_stage_two_stages(self):
        stages = [
            Stage(name="build", base_image="golang:1.22", instructions=["RUN go build -o /app"]),
            Stage(name="runtime", base_image="alpine:3.19", instructions=["COPY --from=build /app /app"]),
        ]
        result = self.gen.multi_stage(stages)
        self.assertIn("AS build", result)
        self.assertIn("AS runtime", result)
        self.assertIn("COPY --from=build", result)

    def test_multi_stage_empty_raises(self):
        with self.assertRaises(ValueError):
            self.gen.multi_stage([])

    # -- optimize ----------------------------------------------------------

    def test_optimize_collapses_runs(self):
        df = "FROM python:3.12\nRUN apt-get update\nRUN apt-get install -y curl\n"
        result = self.gen.optimize(df)
        self.assertEqual(result.count("RUN "), 1)
        self.assertIn("&&", result)

    def test_optimize_adds_no_cache_dir(self):
        df = "FROM python:3.12\nRUN pip install flask\n"
        result = self.gen.optimize(df)
        self.assertIn("--no-cache-dir", result)

    def test_optimize_adds_omit_dev(self):
        df = "FROM node:20\nRUN npm ci\n"
        result = self.gen.optimize(df)
        self.assertIn("--omit=dev", result)

    def test_optimize_preserves_existing_no_cache(self):
        df = "FROM python:3.12\nRUN pip install --no-cache-dir flask\n"
        result = self.gen.optimize(df)
        self.assertEqual(result.count("--no-cache-dir"), 1)

    # -- security_scan -----------------------------------------------------

    def test_scan_detects_latest_tag(self):
        df = "FROM python:latest\nCOPY . .\n"
        warnings = self.gen.security_scan(df)
        self.assertTrue(any("latest" in w for w in warnings))

    def test_scan_detects_no_user(self):
        df = "FROM python:3.12\nCOPY . .\n"
        warnings = self.gen.security_scan(df)
        self.assertTrue(any("root" in w.lower() for w in warnings))

    def test_scan_detects_secret_in_env(self):
        df = "FROM python:3.12\nENV DB_PASSWORD=secret123\n"
        warnings = self.gen.security_scan(df)
        self.assertTrue(any("secret" in w.lower() or "PASSWORD" in w for w in warnings))

    def test_scan_no_issues(self):
        df = "FROM python:3.12-slim\nWORKDIR /app\nCOPY . .\nUSER appuser\n"
        warnings = self.gen.security_scan(df)
        # Should be clean (non-root USER is present, version pinned)
        self.assertEqual(len(warnings), 0)

    def test_scan_detects_curl_pipe_bash(self):
        df = "FROM ubuntu:22.04\nRUN curl -sSL https://example.com | bash\nUSER app\n"
        warnings = self.gen.security_scan(df)
        self.assertTrue(any("curl" in w.lower() for w in warnings))


if __name__ == "__main__":
    unittest.main()
