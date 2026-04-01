"""Tests for lidco.ecosystem.actions_generator."""

from lidco.ecosystem.actions_generator import (
    ActionsGenerator,
    CacheConfig,
    Job,
    JobType,
    MatrixEntry,
)


class TestDataclasses:
    def test_matrix_entry_frozen(self):
        m = MatrixEntry(key="python-version", values=("3.11", "3.12"))
        assert m.key == "python-version"
        assert m.values == ("3.11", "3.12")

    def test_cache_config_frozen(self):
        c = CacheConfig(paths=("~/.cache/pip",), key="pip-key")
        assert c.paths == ("~/.cache/pip",)
        assert c.key == "pip-key"

    def test_job_frozen(self):
        j = Job(name="test", job_type=JobType.TEST, steps=("step1",))
        assert j.name == "test"
        assert j.job_type == JobType.TEST
        assert j.steps == ("step1",)
        assert j.matrix == ()
        assert j.cache is None
        assert j.needs == ()

    def test_job_type_values(self):
        assert JobType.TEST.value == "test"
        assert JobType.LINT.value == "lint"
        assert JobType.BUILD.value == "build"
        assert JobType.DEPLOY.value == "deploy"
        assert JobType.SECURITY.value == "security"


class TestDetectProject:
    def test_detect_python_pyproject(self):
        gen = ActionsGenerator()
        result = gen.detect_project(["src/main.py", "pyproject.toml"])
        assert result["type"] == "python"

    def test_detect_python_setup_py(self):
        gen = ActionsGenerator()
        result = gen.detect_project(["setup.py", "README.md"])
        assert result["type"] == "python"

    def test_detect_node(self):
        gen = ActionsGenerator()
        result = gen.detect_project(["package.json", "index.js"])
        assert result["type"] == "node"

    def test_detect_rust(self):
        gen = ActionsGenerator()
        result = gen.detect_project(["Cargo.toml", "src/main.rs"])
        assert result["type"] == "rust"

    def test_detect_go(self):
        gen = ActionsGenerator()
        result = gen.detect_project(["go.mod", "main.go"])
        assert result["type"] == "go"

    def test_detect_unknown(self):
        gen = ActionsGenerator()
        result = gen.detect_project(["Makefile", "README.md"])
        assert result["type"] == "unknown"

    def test_detect_files_preserved(self):
        gen = ActionsGenerator()
        files = ["a.txt", "b.txt"]
        result = gen.detect_project(files)
        assert result["files"] == ("a.txt", "b.txt")


class TestGenerateJobs:
    def test_generate_test_job_python(self):
        gen = ActionsGenerator()
        job = gen.generate_test_job("python")
        assert job.job_type == JobType.TEST
        assert job.name == "test"
        assert "pytest -q" in job.steps
        assert job.matrix[0].key == "python-version"
        assert job.cache is not None
        assert "pip" in job.cache.paths[0]

    def test_generate_test_job_custom_versions(self):
        gen = ActionsGenerator()
        job = gen.generate_test_job("python", python_versions=("3.10", "3.13"))
        assert job.matrix[0].values == ("3.10", "3.13")

    def test_generate_test_job_node(self):
        gen = ActionsGenerator()
        job = gen.generate_test_job("node")
        assert "npm test" in job.steps
        assert job.cache is not None

    def test_generate_test_job_rust(self):
        gen = ActionsGenerator()
        job = gen.generate_test_job("rust")
        assert "cargo test" in job.steps

    def test_generate_test_job_go(self):
        gen = ActionsGenerator()
        job = gen.generate_test_job("go")
        assert "go test ./..." in job.steps

    def test_generate_test_job_unknown(self):
        gen = ActionsGenerator()
        job = gen.generate_test_job("java")
        assert "echo 'No test runner configured'" in job.steps

    def test_generate_lint_job_python(self):
        gen = ActionsGenerator()
        job = gen.generate_lint_job("python")
        assert job.job_type == JobType.LINT
        assert "ruff check ." in job.steps

    def test_generate_lint_job_node(self):
        gen = ActionsGenerator()
        job = gen.generate_lint_job("node")
        assert "npm run lint" in job.steps

    def test_generate_lint_job_rust(self):
        gen = ActionsGenerator()
        job = gen.generate_lint_job("rust")
        assert "cargo clippy" in job.steps

    def test_generate_lint_job_unknown(self):
        gen = ActionsGenerator()
        job = gen.generate_lint_job("unknown")
        assert "echo 'No linter configured'" in job.steps

    def test_generate_build_job_python(self):
        gen = ActionsGenerator()
        job = gen.generate_build_job("python")
        assert job.job_type == JobType.BUILD
        assert "python -m build" in job.steps
        assert job.needs == ("test",)

    def test_generate_build_job_node(self):
        gen = ActionsGenerator()
        job = gen.generate_build_job("node")
        assert "npm run build" in job.steps

    def test_generate_deploy_job(self):
        gen = ActionsGenerator()
        job = gen.generate_deploy_job("vercel")
        assert job.job_type == JobType.DEPLOY
        assert "deploy to vercel" in job.steps
        assert job.needs == ("build",)

    def test_generate_deploy_job_custom_target(self):
        gen = ActionsGenerator()
        job = gen.generate_deploy_job("netlify")
        assert "deploy to netlify" in job.steps

    def test_generate_security_job(self):
        gen = ActionsGenerator()
        job = gen.generate_security_job()
        assert job.job_type == JobType.SECURITY
        assert "github/codeql-action/init@v3" in job.steps

    def test_jobs_accumulate_immutably(self):
        gen = ActionsGenerator()
        gen.generate_test_job("python")
        gen.generate_lint_job("python")
        assert len(gen._jobs) == 2


class TestYamlAndSummary:
    def test_to_yaml_basic_structure(self):
        gen = ActionsGenerator()
        job = gen.generate_test_job("python")
        yaml = gen.to_yaml([job])
        assert "name: CI" in yaml
        assert "on:" in yaml
        assert "jobs:" in yaml
        assert "  test:" in yaml
        assert "runs-on: ubuntu-latest" in yaml

    def test_to_yaml_uses_vs_run(self):
        gen = ActionsGenerator()
        job = gen.generate_test_job("python")
        yaml = gen.to_yaml([job])
        assert "- uses: actions/checkout@v4" in yaml
        assert "- run: pytest -q" in yaml

    def test_to_yaml_matrix(self):
        gen = ActionsGenerator()
        job = gen.generate_test_job("python")
        yaml = gen.to_yaml([job])
        assert "strategy:" in yaml
        assert "matrix:" in yaml
        assert "python-version:" in yaml

    def test_to_yaml_needs(self):
        gen = ActionsGenerator()
        job = gen.generate_build_job("python")
        yaml = gen.to_yaml([job])
        assert "needs: [test]" in yaml

    def test_to_yaml_cache_comment(self):
        gen = ActionsGenerator()
        job = gen.generate_test_job("python")
        yaml = gen.to_yaml([job])
        assert "# cache: key=" in yaml

    def test_summary_no_jobs(self):
        gen = ActionsGenerator()
        assert gen.summary([]) == "No jobs configured."

    def test_summary_with_jobs(self):
        gen = ActionsGenerator()
        jobs = [gen.generate_test_job("python"), gen.generate_build_job("python")]
        s = gen.summary(jobs)
        assert "2 job(s)" in s
        assert "test [test]" in s
        assert "(needs: test)" in s
