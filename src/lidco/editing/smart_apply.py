"""Smart code block applier -- extracts fenced code from LLM text and applies to target files."""

import difflib
import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ApplyCandidate:
    file_path: str
    confidence: float  # 0.0-1.0
    reason: str  # "fence_path", "function_match", "extension_match"
    language: str


@dataclass
class SmartApplyResult:
    file_path: str
    applied: bool
    diff_preview: str  # unified diff
    error: str = ""


class SmartApply:
    MIN_CONFIDENCE = 0.3

    def __init__(self, project_root: str = ".") -> None:
        self.project_root = Path(project_root).resolve()

    def extract_code_blocks(self, text: str) -> list[tuple[str, str]]:
        """Parse triple-backtick fenced blocks.

        Returns list of (fence_info, code).
        fence_info is the text after the opening backticks (e.g., 'python', 'src/foo.py').
        """
        pattern = r"```([^\n]*)\n(.*?)```"
        matches = re.findall(pattern, text, re.DOTALL)
        return [(info.strip(), code) for info, code in matches]

    def detect_language(self, fence_info: str, code: str) -> str:
        """Infer language from fence info or code content."""
        info_lower = fence_info.lower()

        lang_map = {
            "python": "python",
            "py": "python",
            "javascript": "javascript",
            "js": "javascript",
            "typescript": "typescript",
            "ts": "typescript",
            "go": "go",
            "rust": "rust",
            "java": "java",
            "cpp": "cpp",
            "c": "c",
            "ruby": "ruby",
            "bash": "bash",
            "sh": "sh",
        }

        for token, lang in lang_map.items():
            if token in info_lower:
                return lang

        ext_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".go": "go",
            ".rs": "rust",
            ".java": "java",
        }
        for ext, lang in ext_map.items():
            if fence_info.endswith(ext):
                return lang

        if "def " in code or ("import " in code and ":" in code):
            return "python"
        if "function " in code or "const " in code or "=>" in code:
            return "javascript"

        return "unknown"

    def find_target_file(
        self, code: str, language: str, hint: str = ""
    ) -> "ApplyCandidate | None":
        """Find the best target file for this code block.

        Priority:
        1. hint is a valid file path (confidence=1.0)
        2. hint contains a path-like string with extension (confidence=0.9)
        3. Scan project for files matching a function/class name in code (confidence=0.6)
        4. Extension-only match (first file with matching extension) (confidence=0.3)
        """
        lang_exts = {
            "python": ".py",
            "py": ".py",
            "javascript": ".js",
            "js": ".js",
            "typescript": ".ts",
            "ts": ".ts",
            "go": ".go",
            "rust": ".rs",
        }
        ext = lang_exts.get(language, "")

        # Signal 1: hint is a file path
        if hint:
            hint_path = self.project_root / hint
            if hint_path.exists():
                return ApplyCandidate(str(hint_path), 1.0, "fence_path", language)
            # Partial path match
            if "." in hint or "/" in hint:
                matches = list(self.project_root.rglob(hint.lstrip("./")))
                if matches:
                    return ApplyCandidate(
                        str(matches[0]), 0.9, "fence_path", language
                    )

        # Signal 2: Extract function/class names from code, search in project
        if ext:
            names = re.findall(r"(?:def|class|func|function)\s+(\w+)", code)
            if names:
                for src_file in self.project_root.rglob(f"*{ext}"):
                    try:
                        content = src_file.read_text(
                            encoding="utf-8", errors="ignore"
                        )
                        for name in names:
                            if name in content:
                                return ApplyCandidate(
                                    str(src_file), 0.6, "function_match", language
                                )
                    except OSError:
                        continue

        # Signal 3: First file with matching extension
        if ext:
            for src_file in self.project_root.rglob(f"*{ext}"):
                return ApplyCandidate(
                    str(src_file), 0.3, "extension_match", language
                )

        return None

    def apply_block(
        self, code: str, target: str, dry_run: bool = False
    ) -> SmartApplyResult:
        """Write code to target file. Returns unified diff preview."""
        target_path = Path(target)

        # Security: must be within project root
        try:
            target_path.resolve().relative_to(self.project_root)
        except ValueError:
            return SmartApplyResult(target, False, "", "Target file is outside project root")

        original = ""
        if target_path.exists():
            try:
                original = target_path.read_text(encoding="utf-8")
            except OSError as exc:
                return SmartApplyResult(target, False, "", str(exc))

        diff = "\n".join(
            difflib.unified_diff(
                original.splitlines(),
                code.splitlines(),
                fromfile=f"{target} (original)",
                tofile=f"{target} (proposed)",
                lineterm="",
            )
        )

        if not dry_run:
            try:
                target_path.parent.mkdir(parents=True, exist_ok=True)
                target_path.write_text(code, encoding="utf-8")
            except OSError as exc:
                return SmartApplyResult(target, False, diff, str(exc))

        return SmartApplyResult(target, not dry_run, diff)

    def apply_all(
        self, text: str, dry_run: bool = False
    ) -> list[SmartApplyResult]:
        """Process all code blocks in LLM response text."""
        blocks = self.extract_code_blocks(text)
        results: list[SmartApplyResult] = []
        for fence_info, code in blocks:
            if not code.strip():
                continue
            language = self.detect_language(fence_info, code)
            candidate = self.find_target_file(code, language, hint=fence_info)
            if candidate is None or candidate.confidence < self.MIN_CONFIDENCE:
                continue
            result = self.apply_block(code, candidate.file_path, dry_run=dry_run)
            results.append(result)
        return results
