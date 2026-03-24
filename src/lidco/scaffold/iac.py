"""IaCScaffolder — generate Dockerfiles, Compose files, and Terraform configs."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass
class ScaffoldResult:
    files: dict[str, str]  # filename -> content
    description: str
    template_used: str


class IaCScaffolder:
    """Generate IaC scaffolding from templates or an LLM function."""

    def __init__(self, llm_fn: Callable[[str], str] | None = None) -> None:
        self._llm_fn = llm_fn

    # ------------------------------------------------------------------
    # High-level generators
    # ------------------------------------------------------------------

    def generate_dockerfile(
        self,
        language: str,
        framework: str = "",
        extras: list[str] | None = None,
    ) -> ScaffoldResult:
        content = self.dockerfile_template(language, framework)
        return ScaffoldResult(
            files={"Dockerfile": content},
            description=f"Dockerfile for {language}{(' + ' + framework) if framework else ''}",
            template_used="dockerfile",
        )

    def generate_compose(self, services: list[dict]) -> ScaffoldResult:
        content = self.compose_template(services)
        return ScaffoldResult(
            files={"docker-compose.yml": content},
            description=f"Docker Compose for {len(services)} service(s)",
            template_used="compose",
        )

    def generate_terraform(self, provider: str, resources: list[dict]) -> ScaffoldResult:
        main_tf = self.terraform_template(provider, resources)
        return ScaffoldResult(
            files={"main.tf": main_tf, "variables.tf": ""},
            description=f"Terraform config for provider {provider}",
            template_used="terraform",
        )

    def generate_from_description(self, description: str) -> ScaffoldResult:
        """Generate from a free-text description using LLM or keyword matching."""
        if self._llm_fn is not None:
            result = self._llm_fn(description)
            if isinstance(result, ScaffoldResult):
                return result
            # LLM returned a string — wrap it
            return ScaffoldResult(
                files={"scaffold.txt": str(result)},
                description=description,
                template_used="llm",
            )

        lower = description.lower()

        if "terraform" in lower or " tf" in lower:
            return self.generate_terraform("aws", [])

        if "compose" in lower or "docker-compose" in lower:
            return self.generate_compose([])

        # Language detection
        for lang in ("python", "node", "go", "rust", "java"):
            if lang in lower:
                return self.generate_dockerfile(lang)

        # Default to python
        return self.generate_dockerfile("python")

    # ------------------------------------------------------------------
    # Templates
    # ------------------------------------------------------------------

    @staticmethod
    def dockerfile_template(language: str, framework: str = "") -> str:
        lang = language.lower()

        if lang == "python":
            return (
                "FROM python:3.13-slim\n"
                "WORKDIR /app\n"
                "COPY requirements.txt .\n"
                "RUN pip install --no-cache-dir -r requirements.txt\n"
                "COPY . .\n"
                'CMD ["python", "main.py"]\n'
            )

        if lang == "node":
            return (
                "FROM node:20-alpine\n"
                "WORKDIR /app\n"
                "COPY package*.json .\n"
                "RUN npm ci\n"
                "COPY . .\n"
                'CMD ["node", "index.js"]\n'
            )

        if lang == "go":
            return (
                "FROM golang:1.22-alpine AS builder\n"
                "WORKDIR /app\n"
                "COPY . .\n"
                "RUN go build -o main .\n\n"
                "FROM alpine:latest\n"
                "WORKDIR /app\n"
                "COPY --from=builder /app/main .\n"
                'CMD ["./main"]\n'
            )

        if lang == "rust":
            return (
                "FROM rust:1.75-slim AS builder\n"
                "WORKDIR /app\n"
                "COPY . .\n"
                "RUN cargo build --release\n\n"
                "FROM debian:bookworm-slim\n"
                "WORKDIR /app\n"
                "COPY --from=builder /app/target/release/app .\n"
                'CMD ["./app"]\n'
            )

        if lang == "java":
            return (
                "FROM eclipse-temurin:21-jdk-alpine AS builder\n"
                "WORKDIR /app\n"
                "COPY . .\n"
                "RUN ./mvnw package -DskipTests\n\n"
                "FROM eclipse-temurin:21-jre-alpine\n"
                "WORKDIR /app\n"
                "COPY --from=builder /app/target/*.jar app.jar\n"
                'CMD ["java", "-jar", "app.jar"]\n'
            )

        # Generic fallback
        return f"# Dockerfile for {language}\nFROM {language}:latest\nWORKDIR /app\nCOPY . .\n"

    @staticmethod
    def compose_template(services: list[dict]) -> str:
        lines = ['version: "3.9"', "services:"]
        for svc in services:
            name = svc.get("name", "app")
            image = svc.get("image", "")
            ports = svc.get("ports", "")
            env = svc.get("env", "")

            lines.append(f"  {name}:")
            if image:
                lines.append(f"    image: {image}")
            if ports:
                lines.append("    ports:")
                lines.append(f"      - \"{ports}\"")
            if env:
                lines.append("    environment:")
                lines.append(f"      - {env}")

        return "\n".join(lines) + "\n"

    @staticmethod
    def terraform_template(provider: str, resources: list[dict]) -> str:
        lines: list[str] = [
            'terraform {',
            '  required_version = ">= 1.0"',
            '}',
            '',
        ]

        prov = provider.lower()
        if prov == "aws":
            lines += [
                'provider "aws" {',
                '  region = "us-east-1"',
                '}',
                '',
            ]
        elif prov == "gcp":
            lines += [
                'provider "google" {',
                '  project = "my-project"',
                '}',
                '',
            ]
        elif prov == "azure":
            lines += [
                'provider "azurerm" {',
                '  features {}',
                '}',
                '',
            ]
        else:
            lines += [
                f'provider "{prov}" {{',
                '}',
                '',
            ]

        for res in resources:
            rtype = res.get("type", "resource")
            rname = res.get("name", "main")
            lines += [
                f'resource "{rtype}" "{rname}" {{',
                '}',
                '',
            ]

        return "\n".join(lines)
