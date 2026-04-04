"""DockerfileGenerator — generate, optimize, and scan Dockerfiles (stdlib only)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field


# ------------------------------------------------------------------ #
# Language / framework presets                                         #
# ------------------------------------------------------------------ #

_BASE_IMAGES: dict[str, str] = {
    "python": "python:3.12-slim",
    "node": "node:20-alpine",
    "go": "golang:1.22-alpine",
    "rust": "rust:1.77-slim",
    "java": "eclipse-temurin:21-jdk-alpine",
    "ruby": "ruby:3.3-slim",
}

_FRAMEWORK_SETUP: dict[str, list[str]] = {
    "flask": [
        "COPY requirements.txt .",
        "RUN pip install --no-cache-dir -r requirements.txt",
        "COPY . .",
        'CMD ["python", "-m", "flask", "run", "--host=0.0.0.0"]',
    ],
    "django": [
        "COPY requirements.txt .",
        "RUN pip install --no-cache-dir -r requirements.txt",
        "COPY . .",
        'CMD ["gunicorn", "app.wsgi:application", "--bind", "0.0.0.0:8000"]',
    ],
    "express": [
        "COPY package*.json ./",
        "RUN npm ci --omit=dev",
        "COPY . .",
        'CMD ["node", "server.js"]',
    ],
    "fastapi": [
        "COPY requirements.txt .",
        "RUN pip install --no-cache-dir -r requirements.txt",
        "COPY . .",
        'CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]',
    ],
    "nextjs": [
        "COPY package*.json ./",
        "RUN npm ci",
        "COPY . .",
        "RUN npm run build",
        'CMD ["npm", "start"]',
    ],
    "gin": [
        "COPY go.mod go.sum ./",
        "RUN go mod download",
        "COPY . .",
        "RUN go build -o /app .",
        'CMD ["/app"]',
    ],
}

# Default ports per framework
_DEFAULT_PORTS: dict[str, int] = {
    "flask": 5000,
    "django": 8000,
    "express": 3000,
    "fastapi": 8000,
    "nextjs": 3000,
    "gin": 8080,
}


@dataclass
class Stage:
    """One stage in a multi-stage Dockerfile."""

    name: str
    base_image: str
    instructions: list[str] = field(default_factory=list)


class DockerfileGenerator:
    """Generate, optimize, and scan Dockerfiles."""

    def __init__(self) -> None:
        self._base_images: dict[str, str] = dict(_BASE_IMAGES)
        self._framework_setup: dict[str, list[str]] = {
            k: list(v) for k, v in _FRAMEWORK_SETUP.items()
        }

    # ------------------------------------------------------------------ #
    # Public API                                                          #
    # ------------------------------------------------------------------ #

    def generate(self, language: str, framework: str | None = None) -> str:
        """Return a Dockerfile string for *language* and optional *framework*."""
        lang = language.lower()
        base = self._base_images.get(lang)
        if base is None:
            raise ValueError(f"Unsupported language: {language}")

        lines: list[str] = [f"FROM {base}"]
        lines.append("WORKDIR /app")

        fw = (framework or "").lower()
        if fw and fw in self._framework_setup:
            lines.extend(self._framework_setup[fw])
            port = _DEFAULT_PORTS.get(fw)
            if port:
                lines.append(f"EXPOSE {port}")
        else:
            lines.append("COPY . .")

        return "\n".join(lines) + "\n"

    def multi_stage(self, stages: list[Stage]) -> str:
        """Return a multi-stage Dockerfile from *stages*."""
        if not stages:
            raise ValueError("At least one stage is required")
        parts: list[str] = []
        for stage in stages:
            parts.append(f"FROM {stage.base_image} AS {stage.name}")
            for instr in stage.instructions:
                parts.append(instr)
            parts.append("")
        return "\n".join(parts).rstrip() + "\n"

    def optimize(self, dockerfile: str) -> str:
        """Return an optimized Dockerfile string.

        Optimizations:
        - Collapse consecutive RUN lines into a single ``RUN`` with ``&&``
        - Add ``--no-cache-dir`` to pip install if missing
        - Add ``--omit=dev`` to npm ci if missing
        """
        lines = dockerfile.splitlines()
        out: list[str] = []
        run_buffer: list[str] = []

        def _flush_runs() -> None:
            if not run_buffer:
                return
            if len(run_buffer) == 1:
                out.append(f"RUN {run_buffer[0]}")
            else:
                joined = " && \\\n    ".join(run_buffer)
                out.append(f"RUN {joined}")
            run_buffer.clear()

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("RUN "):
                cmd = stripped[4:].strip()
                # pip optimisation
                if "pip install" in cmd and "--no-cache-dir" not in cmd:
                    cmd = cmd.replace("pip install", "pip install --no-cache-dir", 1)
                # npm optimisation
                if "npm ci" in cmd and "--omit=dev" not in cmd and "--production" not in cmd:
                    cmd = cmd.replace("npm ci", "npm ci --omit=dev", 1)
                run_buffer.append(cmd)
            else:
                _flush_runs()
                out.append(line)

        _flush_runs()
        return "\n".join(out) + "\n" if out else ""

    def security_scan(self, dockerfile: str) -> list[str]:
        """Return a list of security warnings for *dockerfile*."""
        warnings: list[str] = []
        lines = dockerfile.splitlines()
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            # Running as root
            if stripped.startswith("USER root"):
                warnings.append(f"Line {i}: Running as root is not recommended")
            # Using latest tag
            if re.match(r"FROM\s+\S+:latest", stripped):
                warnings.append(f"Line {i}: Avoid using ':latest' tag, pin a specific version")
            # No pinned version at all
            if re.match(r"FROM\s+\S+$", stripped) and ":" not in stripped.split()[-1] and "AS" not in stripped.upper():
                warnings.append(f"Line {i}: Base image has no version tag, pin a specific version")
            # COPY or ADD from parent
            if re.match(r"(COPY|ADD)\s+\.\.", stripped):
                warnings.append(f"Line {i}: COPY/ADD from parent directory may leak files")
            # Secrets in ENV
            if re.match(r"ENV\s+\S*(PASSWORD|SECRET|TOKEN|KEY)\S*\s*=", stripped, re.IGNORECASE):
                warnings.append(f"Line {i}: Potential secret in ENV variable")
            # curl | bash pattern
            if "curl" in stripped and ("bash" in stripped or "sh" in stripped) and "|" in stripped:
                warnings.append(f"Line {i}: Piping curl to shell is a security risk")
        # Check if USER is set anywhere
        has_user = any(l.strip().startswith("USER ") for l in lines if not l.strip().startswith("USER root"))
        if not has_user:
            warnings.append("No non-root USER directive found; container will run as root")
        return warnings
