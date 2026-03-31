"""Q140 — ArgParser: argument parsing with type coercion."""
from __future__ import annotations

import shlex
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ParsedArgs:
    """Result of parsing arguments."""

    positional: list[str] = field(default_factory=list)
    flags: dict[str, bool] = field(default_factory=dict)
    options: dict[str, str] = field(default_factory=dict)
    raw: str = ""
    errors: list[str] = field(default_factory=list)


@dataclass
class ArgSpec:
    """Specification for a single argument."""

    name: str
    type: str = "str"
    required: bool = False
    default: Any = None
    help: str = ""


class ArgParser:
    """Parse a CLI argument string into structured ParsedArgs."""

    _COERCE = {
        "str": str,
        "int": int,
        "float": float,
        "bool": lambda v: v.lower() in ("true", "1", "yes", "on"),
    }

    def __init__(self, command_name: str) -> None:
        self._command_name = command_name
        self._positionals: list[ArgSpec] = []
        self._flags: dict[str, ArgSpec] = {}
        self._options: dict[str, ArgSpec] = {}
        self._short_map: dict[str, str] = {}

    # ---- builder -----------------------------------------------------------

    def add_positional(
        self, name: str, type: str = "str", required: bool = True, help: str = "", default: Any = None
    ) -> None:
        self._positionals.append(
            ArgSpec(name=name, type=type, required=required, default=default, help=help)
        )

    def add_flag(self, name: str, short: Optional[str] = None, help: str = "") -> None:
        spec = ArgSpec(name=name, type="bool", help=help)
        self._flags[f"--{name}"] = spec
        if short:
            self._short_map[f"-{short}"] = f"--{name}"

    def add_option(
        self,
        name: str,
        type: str = "str",
        default: Any = None,
        required: bool = False,
        short: Optional[str] = None,
        help: str = "",
    ) -> None:
        spec = ArgSpec(name=name, type=type, required=required, default=default, help=help)
        self._options[f"--{name}"] = spec
        if short:
            self._short_map[f"-{short}"] = f"--{name}"

    # ---- parsing -----------------------------------------------------------

    def parse(self, args_str: str) -> ParsedArgs:
        result = ParsedArgs(raw=args_str)
        try:
            tokens = shlex.split(args_str)
        except ValueError as exc:
            result.errors.append(f"Parse error: {exc}")
            return result

        positional_vals: list[str] = []
        i = 0
        while i < len(tokens):
            tok = tokens[i]
            canonical = self._short_map.get(tok, tok)

            if canonical in self._flags:
                result.flags[self._flags[canonical].name] = True
                i += 1
                continue

            if canonical in self._options:
                spec = self._options[canonical]
                if i + 1 >= len(tokens):
                    result.errors.append(f"Option {tok} requires a value")
                    i += 1
                    continue
                raw_val = tokens[i + 1]
                coerced = self._coerce(raw_val, spec.type)
                if coerced is None:
                    result.errors.append(
                        f"Cannot convert '{raw_val}' to {spec.type} for {tok}"
                    )
                else:
                    result.options[spec.name] = coerced
                i += 2
                continue

            positional_vals.append(tok)
            i += 1

        # Map positional values to specs
        for idx, spec in enumerate(self._positionals):
            if idx < len(positional_vals):
                coerced = self._coerce(positional_vals[idx], spec.type)
                if coerced is None:
                    result.errors.append(
                        f"Cannot convert '{positional_vals[idx]}' to {spec.type} for {spec.name}"
                    )
                else:
                    result.positional.append(str(coerced))
            elif spec.required:
                result.errors.append(f"Missing required argument: {spec.name}")
            elif spec.default is not None:
                result.positional.append(str(spec.default))

        # Extra positionals beyond specs are kept
        if len(positional_vals) > len(self._positionals):
            for extra in positional_vals[len(self._positionals):]:
                result.positional.append(extra)

        # Apply flag defaults (False for unset)
        for key, spec in self._flags.items():
            if spec.name not in result.flags:
                result.flags[spec.name] = False

        # Apply option defaults
        for key, spec in self._options.items():
            if spec.name not in result.options and spec.default is not None:
                result.options[spec.name] = spec.default
            if spec.required and spec.name not in result.options:
                result.errors.append(f"Missing required option: --{spec.name}")

        return result

    def _coerce(self, value: str, type_name: str) -> Any:
        fn = self._COERCE.get(type_name)
        if fn is None:
            return value
        try:
            return fn(value)
        except (ValueError, TypeError):
            return None

    # ---- help --------------------------------------------------------------

    def usage(self) -> str:
        parts = [f"Usage: /{self._command_name}"]
        for spec in self._positionals:
            if spec.required:
                parts.append(f"<{spec.name}>")
            else:
                parts.append(f"[{spec.name}]")
        for key, spec in self._options.items():
            short = self._find_short(key)
            label = f"{short}|{key}" if short else key
            if spec.required:
                parts.append(f"{label} <{spec.name}>")
            else:
                parts.append(f"[{label} <{spec.name}>]")
        for key, spec in self._flags.items():
            short = self._find_short(key)
            label = f"{short}|{key}" if short else key
            parts.append(f"[{label}]")
        return " ".join(parts)

    def help_text(self) -> str:
        lines = [self.usage(), ""]
        if self._positionals:
            lines.append("Positional arguments:")
            for spec in self._positionals:
                default_info = f" (default: {spec.default})" if spec.default is not None else ""
                lines.append(f"  {spec.name:<20} {spec.help}{default_info}")
            lines.append("")
        if self._options:
            lines.append("Options:")
            for key, spec in self._options.items():
                short = self._find_short(key)
                label = f"{short}, {key}" if short else f"    {key}"
                default_info = f" (default: {spec.default})" if spec.default is not None else ""
                lines.append(f"  {label:<20} {spec.help}{default_info}")
            lines.append("")
        if self._flags:
            lines.append("Flags:")
            for key, spec in self._flags.items():
                short = self._find_short(key)
                label = f"{short}, {key}" if short else f"    {key}"
                lines.append(f"  {label:<20} {spec.help}")
        return "\n".join(lines)

    def _find_short(self, long_key: str) -> Optional[str]:
        for short, long_ in self._short_map.items():
            if long_ == long_key:
                return short
        return None
