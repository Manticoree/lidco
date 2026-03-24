"""Tests for DeploymentScaffolder — T584."""
import json
from pathlib import Path

import pytest

from lidco.scaffold.deploy import DeploymentBundle, DeploymentScaffolder, ProjectProfile


# ── Detection tests ─────────────────────────────────────────────────


class TestDetectPython:
    def test_detect_python_via_requirements(self, tmp_path: Path):
        (tmp_path / "requirements.txt").write_text("fastapi\nuvicorn\n")
        (tmp_path / "main.py").write_text("from fastapi import FastAPI\napp = FastAPI()")
        profile = DeploymentScaffolder(tmp_path).detect_project()
        assert profile.language == "python"

    def test_detect_fastapi_framework(self, tmp_path: Path):
        (tmp_path / "requirements.txt").write_text("fastapi\nuvicorn\n")
        profile = DeploymentScaffolder(tmp_path).detect_project()
        assert profile.framework == "fastapi"

    def test_detect_flask_framework(self, tmp_path: Path):
        (tmp_path / "requirements.txt").write_text("flask\ngunicorn\n")
        profile = DeploymentScaffolder(tmp_path).detect_project()
        assert profile.framework == "flask"

    def test_detect_django_framework(self, tmp_path: Path):
        (tmp_path / "requirements.txt").write_text("django\npsycopg2\n")
        profile = DeploymentScaffolder(tmp_path).detect_project()
        assert profile.framework == "django"

    def test_detect_python_via_pyproject(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text(
            '[tool.poetry.dependencies]\npython = "^3.11"\nfastapi = "^0.100"\n'
        )
        profile = DeploymentScaffolder(tmp_path).detect_project()
        assert profile.language == "python"
        assert profile.framework == "fastapi"

    def test_poetry_package_manager(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text(
            "[tool.poetry]\nname = \"app\"\n"
        )
        profile = DeploymentScaffolder(tmp_path).detect_project()
        assert profile.package_manager == "poetry"

    def test_pip_package_manager(self, tmp_path: Path):
        (tmp_path / "requirements.txt").write_text("flask\n")
        profile = DeploymentScaffolder(tmp_path).detect_project()
        assert profile.package_manager == "pip"

    def test_entry_point_main_py(self, tmp_path: Path):
        (tmp_path / "requirements.txt").write_text("flask\n")
        (tmp_path / "main.py").write_text("")
        profile = DeploymentScaffolder(tmp_path).detect_project()
        assert profile.entry_point == "main.py"

    def test_entry_point_app_py(self, tmp_path: Path):
        (tmp_path / "requirements.txt").write_text("flask\n")
        (tmp_path / "app.py").write_text("")
        profile = DeploymentScaffolder(tmp_path).detect_project()
        assert profile.entry_point == "app.py"

    def test_entry_point_fallback(self, tmp_path: Path):
        (tmp_path / "requirements.txt").write_text("flask\n")
        profile = DeploymentScaffolder(tmp_path).detect_project()
        assert profile.entry_point == "main.py"

    def test_python_port_default(self, tmp_path: Path):
        (tmp_path / "requirements.txt").write_text("flask\n")
        profile = DeploymentScaffolder(tmp_path).detect_project()
        assert profile.port == 8000

    def test_has_tests_dir(self, tmp_path: Path):
        (tmp_path / "requirements.txt").write_text("flask\n")
        (tmp_path / "tests").mkdir()
        profile = DeploymentScaffolder(tmp_path).detect_project()
        assert profile.has_tests is True

    def test_has_tests_pytest_ini(self, tmp_path: Path):
        (tmp_path / "requirements.txt").write_text("flask\n")
        (tmp_path / "pytest.ini").write_text("[pytest]\n")
        profile = DeploymentScaffolder(tmp_path).detect_project()
        assert profile.has_tests is True

    def test_no_tests(self, tmp_path: Path):
        (tmp_path / "requirements.txt").write_text("flask\n")
        profile = DeploymentScaffolder(tmp_path).detect_project()
        assert profile.has_tests is False


class TestDetectNode:
    def test_detect_node_project(self, tmp_path: Path):
        (tmp_path / "package.json").write_text(
            json.dumps({"name": "app", "dependencies": {"express": "^4"}})
        )
        profile = DeploymentScaffolder(tmp_path).detect_project()
        assert profile.language == "node"
        assert profile.framework == "express"

    def test_detect_nextjs(self, tmp_path: Path):
        (tmp_path / "package.json").write_text(
            json.dumps({"name": "app", "dependencies": {"next": "^13", "react": "^18"}})
        )
        profile = DeploymentScaffolder(tmp_path).detect_project()
        assert profile.framework == "nextjs"

    def test_node_port_default(self, tmp_path: Path):
        (tmp_path / "package.json").write_text(json.dumps({"name": "app"}))
        profile = DeploymentScaffolder(tmp_path).detect_project()
        assert profile.port == 3000

    def test_yarn_package_manager(self, tmp_path: Path):
        (tmp_path / "package.json").write_text(json.dumps({"name": "app"}))
        (tmp_path / "yarn.lock").write_text("")
        profile = DeploymentScaffolder(tmp_path).detect_project()
        assert profile.package_manager == "yarn"

    def test_pnpm_package_manager(self, tmp_path: Path):
        (tmp_path / "package.json").write_text(json.dumps({"name": "app"}))
        (tmp_path / "pnpm-lock.yaml").write_text("")
        profile = DeploymentScaffolder(tmp_path).detect_project()
        assert profile.package_manager == "pnpm"

    def test_npm_default(self, tmp_path: Path):
        (tmp_path / "package.json").write_text(json.dumps({"name": "app"}))
        profile = DeploymentScaffolder(tmp_path).detect_project()
        assert profile.package_manager == "npm"

    def test_entry_from_main_field(self, tmp_path: Path):
        (tmp_path / "package.json").write_text(
            json.dumps({"name": "app", "main": "server.js"})
        )
        profile = DeploymentScaffolder(tmp_path).detect_project()
        assert profile.entry_point == "server.js"

    def test_entry_fallback(self, tmp_path: Path):
        (tmp_path / "package.json").write_text(json.dumps({"name": "app"}))
        profile = DeploymentScaffolder(tmp_path).detect_project()
        assert profile.entry_point == "src/index.js"

    def test_jest_has_tests(self, tmp_path: Path):
        (tmp_path / "package.json").write_text(
            json.dumps({"name": "app", "devDependencies": {"jest": "^29"}})
        )
        profile = DeploymentScaffolder(tmp_path).detect_project()
        assert profile.has_tests is True

    def test_node_has_db_mongoose(self, tmp_path: Path):
        (tmp_path / "package.json").write_text(
            json.dumps({"name": "app", "dependencies": {"mongoose": "^7"}})
        )
        profile = DeploymentScaffolder(tmp_path).detect_project()
        assert profile.has_db is True

    def test_malformed_package_json(self, tmp_path: Path):
        (tmp_path / "package.json").write_text("{invalid json!!!")
        profile = DeploymentScaffolder(tmp_path).detect_project()
        assert profile.language == "node"
        assert profile.framework == "none"


class TestDetectGo:
    def test_detect_go_project(self, tmp_path: Path):
        (tmp_path / "go.mod").write_text("module myapp\ngo 1.21\n")
        (tmp_path / "main.go").write_text("package main\nfunc main() {}")
        profile = DeploymentScaffolder(tmp_path).detect_project()
        assert profile.language == "go"

    def test_detect_gin(self, tmp_path: Path):
        (tmp_path / "go.mod").write_text("module myapp\nrequire github.com/gin-gonic/gin v1.9\n")
        profile = DeploymentScaffolder(tmp_path).detect_project()
        assert profile.framework == "gin"

    def test_go_port(self, tmp_path: Path):
        (tmp_path / "go.mod").write_text("module myapp\n")
        profile = DeploymentScaffolder(tmp_path).detect_project()
        assert profile.port == 8080

    def test_go_entry(self, tmp_path: Path):
        (tmp_path / "go.mod").write_text("module myapp\n")
        profile = DeploymentScaffolder(tmp_path).detect_project()
        assert profile.entry_point == "main.go"

    def test_go_has_tests(self, tmp_path: Path):
        (tmp_path / "go.mod").write_text("module myapp\n")
        (tmp_path / "main_test.go").write_text("package main")
        profile = DeploymentScaffolder(tmp_path).detect_project()
        assert profile.has_tests is True


class TestDetectRust:
    def test_detect_rust(self, tmp_path: Path):
        (tmp_path / "Cargo.toml").write_text('[package]\nname = "app"\n')
        profile = DeploymentScaffolder(tmp_path).detect_project()
        assert profile.language == "rust"
        assert profile.package_manager == "cargo"
        assert profile.entry_point == "src/main.rs"
        assert profile.port == 8080

    def test_rust_has_tests(self, tmp_path: Path):
        (tmp_path / "Cargo.toml").write_text('[package]\nname = "app"\n')
        (tmp_path / "tests").mkdir()
        profile = DeploymentScaffolder(tmp_path).detect_project()
        assert profile.has_tests is True


class TestDetectUnknown:
    def test_unknown_project(self, tmp_path: Path):
        profile = DeploymentScaffolder(tmp_path).detect_project()
        assert profile.language == "unknown"
        assert profile.framework == "none"
        assert profile.package_manager == "none"
        assert profile.has_tests is False
        assert profile.has_db is False


class TestDetectDB:
    def test_sqlalchemy_detected(self, tmp_path: Path):
        (tmp_path / "requirements.txt").write_text("sqlalchemy\nfastapi\n")
        profile = DeploymentScaffolder(tmp_path).detect_project()
        assert profile.has_db is True

    def test_prisma_detected(self, tmp_path: Path):
        (tmp_path / "package.json").write_text(
            json.dumps({"name": "app", "dependencies": {"prisma": "^5"}})
        )
        profile = DeploymentScaffolder(tmp_path).detect_project()
        assert profile.has_db is True

    def test_no_db(self, tmp_path: Path):
        (tmp_path / "requirements.txt").write_text("flask\nrequests\n")
        profile = DeploymentScaffolder(tmp_path).detect_project()
        assert profile.has_db is False


# ── Dockerfile generation ───────────────────────────────────────────


class TestGenerateDockerfile:
    def test_python_fastapi(self, tmp_path: Path):
        s = DeploymentScaffolder(tmp_path)
        profile = ProjectProfile("python", "fastapi", "pip", "main.py", 8000, False, False)
        df = s.generate_dockerfile(profile)
        assert "FROM python" in df
        assert "8000" in df
        assert "uvicorn" in df

    def test_python_flask(self, tmp_path: Path):
        s = DeploymentScaffolder(tmp_path)
        profile = ProjectProfile("python", "flask", "pip", "app.py", 5000, False, False)
        df = s.generate_dockerfile(profile)
        assert "FROM python" in df
        assert "flask" in df.lower()

    def test_python_django(self, tmp_path: Path):
        s = DeploymentScaffolder(tmp_path)
        profile = ProjectProfile("python", "django", "pip", "manage.py", 8000, False, False)
        df = s.generate_dockerfile(profile)
        assert "gunicorn" in df

    def test_python_poetry(self, tmp_path: Path):
        s = DeploymentScaffolder(tmp_path)
        profile = ProjectProfile("python", "none", "poetry", "main.py", 8000, False, False)
        df = s.generate_dockerfile(profile)
        assert "poetry" in df
        assert "pyproject.toml" in df

    def test_node_express(self, tmp_path: Path):
        s = DeploymentScaffolder(tmp_path)
        profile = ProjectProfile("node", "express", "npm", "src/index.js", 3000, False, False)
        df = s.generate_dockerfile(profile)
        assert "FROM node" in df
        assert "3000" in df
        assert "npm ci" in df

    def test_node_yarn(self, tmp_path: Path):
        s = DeploymentScaffolder(tmp_path)
        profile = ProjectProfile("node", "express", "yarn", "index.js", 3000, False, False)
        df = s.generate_dockerfile(profile)
        assert "yarn" in df

    def test_node_pnpm(self, tmp_path: Path):
        s = DeploymentScaffolder(tmp_path)
        profile = ProjectProfile("node", "express", "pnpm", "index.js", 3000, False, False)
        df = s.generate_dockerfile(profile)
        assert "pnpm" in df

    def test_go(self, tmp_path: Path):
        s = DeploymentScaffolder(tmp_path)
        profile = ProjectProfile("go", "none", "go", "main.go", 8080, False, False)
        df = s.generate_dockerfile(profile)
        assert "FROM golang" in df
        assert "go build" in df

    def test_rust(self, tmp_path: Path):
        s = DeploymentScaffolder(tmp_path)
        profile = ProjectProfile("rust", "none", "cargo", "src/main.rs", 8080, False, False)
        df = s.generate_dockerfile(profile)
        assert "FROM rust" in df
        assert "cargo build" in df

    def test_unknown(self, tmp_path: Path):
        s = DeploymentScaffolder(tmp_path)
        profile = ProjectProfile("unknown", "none", "none", "", 8080, False, False)
        df = s.generate_dockerfile(profile)
        assert "FROM ubuntu" in df


# ── GitHub Actions ──────────────────────────────────────────────────


class TestGenerateGitHubActions:
    def test_python_with_tests(self, tmp_path: Path):
        s = DeploymentScaffolder(tmp_path)
        profile = ProjectProfile("python", "fastapi", "pip", "main.py", 8000, True, False)
        ci = s.generate_github_actions(profile)
        assert "name: CI" in ci
        assert "pytest" in ci
        assert "setup-python" in ci

    def test_python_no_tests(self, tmp_path: Path):
        s = DeploymentScaffolder(tmp_path)
        profile = ProjectProfile("python", "flask", "pip", "app.py", 5000, False, False)
        ci = s.generate_github_actions(profile)
        assert "name: CI" in ci
        assert "pytest" not in ci

    def test_node_with_tests(self, tmp_path: Path):
        s = DeploymentScaffolder(tmp_path)
        profile = ProjectProfile("node", "express", "npm", "index.js", 3000, True, False)
        ci = s.generate_github_actions(profile)
        assert "npm test" in ci

    def test_go_ci(self, tmp_path: Path):
        s = DeploymentScaffolder(tmp_path)
        profile = ProjectProfile("go", "none", "go", "main.go", 8080, True, False)
        ci = s.generate_github_actions(profile)
        assert "go build" in ci
        assert "go test" in ci

    def test_rust_ci(self, tmp_path: Path):
        s = DeploymentScaffolder(tmp_path)
        profile = ProjectProfile("rust", "none", "cargo", "src/main.rs", 8080, True, False)
        ci = s.generate_github_actions(profile)
        assert "cargo build" in ci
        assert "cargo test" in ci

    def test_unknown_ci(self, tmp_path: Path):
        s = DeploymentScaffolder(tmp_path)
        profile = ProjectProfile("unknown", "none", "none", "", 8080, False, False)
        ci = s.generate_github_actions(profile)
        assert "name: CI" in ci


# ── fly.toml ────────────────────────────────────────────────────────


class TestGenerateFlyToml:
    def test_basic(self, tmp_path: Path):
        s = DeploymentScaffolder(tmp_path)
        profile = ProjectProfile("python", "flask", "pip", "app.py", 5000, False, False)
        fly = s.generate_fly_toml(profile)
        assert "http_service" in fly
        assert "5000" in fly
        assert "force_https" in fly

    def test_with_db(self, tmp_path: Path):
        s = DeploymentScaffolder(tmp_path)
        profile = ProjectProfile("python", "django", "pip", "manage.py", 8000, False, True)
        fly = s.generate_fly_toml(profile)
        assert "DATABASE_URL" in fly

    def test_app_name_from_dir(self, tmp_path: Path):
        project = tmp_path / "my-cool-app"
        project.mkdir()
        s = DeploymentScaffolder(project)
        profile = ProjectProfile("node", "express", "npm", "index.js", 3000, False, False)
        fly = s.generate_fly_toml(profile)
        assert 'app = "my-cool-app"' in fly


# ── .env.example ────────────────────────────────────────────────────


class TestGenerateEnvExample:
    def test_python_env(self, tmp_path: Path):
        s = DeploymentScaffolder(tmp_path)
        profile = ProjectProfile("python", "fastapi", "pip", "main.py", 8000, False, False)
        env = s.generate_env_example(profile)
        assert "PORT=8000" in env
        assert "SECRET_KEY" in env
        assert "ENV=production" in env

    def test_node_env(self, tmp_path: Path):
        s = DeploymentScaffolder(tmp_path)
        profile = ProjectProfile("node", "express", "npm", "index.js", 3000, False, False)
        env = s.generate_env_example(profile)
        assert "PORT=3000" in env
        assert "NODE_ENV=production" in env

    def test_db_env(self, tmp_path: Path):
        s = DeploymentScaffolder(tmp_path)
        profile = ProjectProfile("python", "django", "pip", "manage.py", 8000, False, True)
        env = s.generate_env_example(profile)
        assert "DATABASE_URL" in env


# ── Bundle generation (integration) ────────────────────────────────


class TestGenerate:
    def test_returns_bundle(self, tmp_path: Path):
        (tmp_path / "requirements.txt").write_text("fastapi\n")
        s = DeploymentScaffolder(tmp_path)
        bundle = s.generate()
        assert isinstance(bundle, DeploymentBundle)
        assert len(bundle.files) > 0

    def test_bundle_includes_dockerfile(self, tmp_path: Path):
        (tmp_path / "requirements.txt").write_text("flask\n")
        s = DeploymentScaffolder(tmp_path)
        bundle = s.generate()
        assert "Dockerfile" in bundle.files

    def test_bundle_includes_ci(self, tmp_path: Path):
        (tmp_path / "requirements.txt").write_text("flask\n")
        s = DeploymentScaffolder(tmp_path)
        bundle = s.generate()
        assert ".github/workflows/ci.yml" in bundle.files

    def test_bundle_includes_fly(self, tmp_path: Path):
        (tmp_path / "requirements.txt").write_text("flask\n")
        s = DeploymentScaffolder(tmp_path)
        bundle = s.generate()
        assert "fly.toml" in bundle.files

    def test_bundle_includes_env(self, tmp_path: Path):
        (tmp_path / "requirements.txt").write_text("flask\n")
        s = DeploymentScaffolder(tmp_path)
        bundle = s.generate()
        assert ".env.example" in bundle.files

    def test_bundle_has_four_files(self, tmp_path: Path):
        (tmp_path / "requirements.txt").write_text("flask\n")
        s = DeploymentScaffolder(tmp_path)
        bundle = s.generate()
        assert len(bundle.files) == 4

    def test_bundle_profile_attached(self, tmp_path: Path):
        (tmp_path / "requirements.txt").write_text("fastapi\n")
        s = DeploymentScaffolder(tmp_path)
        bundle = s.generate()
        assert bundle.profile.language == "python"
        assert bundle.profile.framework == "fastapi"

    def test_bundle_description(self, tmp_path: Path):
        (tmp_path / "requirements.txt").write_text("fastapi\n")
        s = DeploymentScaffolder(tmp_path)
        bundle = s.generate()
        assert "python" in bundle.description.lower()

    def test_generate_with_explicit_profile(self, tmp_path: Path):
        s = DeploymentScaffolder(tmp_path)
        profile = ProjectProfile("go", "gin", "go", "main.go", 8080, True, False)
        bundle = s.generate(profile)
        assert bundle.profile.language == "go"
        assert "FROM golang" in bundle.files["Dockerfile"]

    def test_generate_node_full(self, tmp_path: Path):
        (tmp_path / "package.json").write_text(
            json.dumps({
                "name": "api",
                "main": "server.js",
                "dependencies": {"express": "^4", "mongoose": "^7"},
                "devDependencies": {"jest": "^29"},
            })
        )
        s = DeploymentScaffolder(tmp_path)
        bundle = s.generate()
        assert bundle.profile.language == "node"
        assert bundle.profile.framework == "express"
        assert bundle.profile.has_db is True
        assert bundle.profile.has_tests is True
        assert "FROM node" in bundle.files["Dockerfile"]
        assert "DATABASE_URL" in bundle.files[".env.example"]
