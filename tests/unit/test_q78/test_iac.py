"""Tests for IaCScaffolder (T513)."""
import pytest

from lidco.scaffold.iac import IaCScaffolder, ScaffoldResult


@pytest.fixture
def scaffolder():
    return IaCScaffolder()


def test_generate_dockerfile_python(scaffolder):
    result = scaffolder.generate_dockerfile("python")
    assert isinstance(result, ScaffoldResult)
    assert "Dockerfile" in result.files
    assert "python" in result.files["Dockerfile"].lower()
    assert result.template_used == "dockerfile"


def test_generate_dockerfile_node(scaffolder):
    result = scaffolder.generate_dockerfile("node")
    assert "node" in result.files["Dockerfile"].lower()


def test_generate_dockerfile_go(scaffolder):
    result = scaffolder.generate_dockerfile("go")
    assert "golang" in result.files["Dockerfile"].lower()


def test_generate_dockerfile_rust(scaffolder):
    result = scaffolder.generate_dockerfile("rust")
    assert "rust" in result.files["Dockerfile"].lower()


def test_generate_dockerfile_java(scaffolder):
    result = scaffolder.generate_dockerfile("java")
    assert "java" in result.files["Dockerfile"].lower()


def test_generate_dockerfile_description(scaffolder):
    result = scaffolder.generate_dockerfile("python", framework="fastapi")
    assert "python" in result.description.lower()


def test_generate_compose_creates_yaml(scaffolder):
    services = [{"name": "api", "image": "nginx", "ports": "80:80"}]
    result = scaffolder.generate_compose(services)
    assert "docker-compose.yml" in result.files
    assert "api" in result.files["docker-compose.yml"]
    assert result.template_used == "compose"


def test_generate_compose_empty_services(scaffolder):
    result = scaffolder.generate_compose([])
    assert "docker-compose.yml" in result.files


def test_generate_terraform_aws(scaffolder):
    result = scaffolder.generate_terraform("aws", [])
    assert "main.tf" in result.files
    assert "aws" in result.files["main.tf"].lower()
    assert result.template_used == "terraform"


def test_generate_terraform_gcp(scaffolder):
    result = scaffolder.generate_terraform("gcp", [])
    assert "google" in result.files["main.tf"]


def test_generate_terraform_azure(scaffolder):
    result = scaffolder.generate_terraform("azure", [])
    assert "azurerm" in result.files["main.tf"]


def test_generate_terraform_includes_variables_tf(scaffolder):
    result = scaffolder.generate_terraform("aws", [])
    assert "variables.tf" in result.files


def test_generate_from_description_python_keyword(scaffolder):
    result = scaffolder.generate_from_description("I need a python Dockerfile")
    assert "Dockerfile" in result.files
    assert "python" in result.files["Dockerfile"].lower()


def test_generate_from_description_terraform_keyword(scaffolder):
    result = scaffolder.generate_from_description("terraform for AWS")
    assert "main.tf" in result.files


def test_generate_from_description_compose_keyword(scaffolder):
    result = scaffolder.generate_from_description("docker-compose for my app")
    assert "docker-compose.yml" in result.files


def test_generate_from_description_uses_llm_fn():
    def my_llm(desc):
        return ScaffoldResult(
            files={"custom.txt": "llm output"},
            description=desc,
            template_used="llm",
        )

    s = IaCScaffolder(llm_fn=my_llm)
    result = s.generate_from_description("anything")
    assert result.template_used == "llm"
    assert "custom.txt" in result.files


def test_generate_from_description_llm_string_wrap():
    def my_llm(desc):
        return "raw string from llm"

    s = IaCScaffolder(llm_fn=my_llm)
    result = s.generate_from_description("x")
    assert result.template_used == "llm"
    assert "scaffold.txt" in result.files
