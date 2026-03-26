"""
Template Engine — lightweight Jinja2-like template rendering.

Supports:
- Variable substitution: {{ variable }} or {{ obj.attr }}
- If/else blocks: {% if condition %}...{% elif condition %}...{% else %}...{% endif %}
- For loops: {% for item in iterable %}...{% endfor %}
- Comments: {# this is ignored #}
- Raw blocks: {% raw %}...{% endraw %}
- File inclusion: {% include "filename.txt" %}
- Filters: {{ value | upper }}, {{ value | lower }}, {{ value | len }}, {{ value | default("x") }}

Stdlib only — no Jinja2 dependency.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class TemplateError(Exception):
    """Raised on template rendering errors."""


class TemplateNotFound(TemplateError):
    """Raised when an included template file is not found."""


# ---------------------------------------------------------------------------
# Template context
# ---------------------------------------------------------------------------

class TemplateContext:
    """
    Variable context for template rendering.

    Supports dot-notation access: {{ user.name }} resolves ctx["user"]["name"]
    or ctx["user"].name (for objects with attributes).
    """

    def __init__(self, variables: dict[str, Any] | None = None) -> None:
        self._vars: dict[str, Any] = dict(variables or {})

    def __setitem__(self, key: str, value: Any) -> None:
        self._vars[key] = value

    def __getitem__(self, key: str) -> Any:
        return self._vars[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self._vars.get(key, default)

    def resolve(self, expr: str) -> Any:
        """Resolve a dot-notation expression in this context."""
        parts = expr.strip().split(".")
        val = self._vars.get(parts[0])
        for part in parts[1:]:
            if val is None:
                return None
            if isinstance(val, dict):
                val = val.get(part)
            else:
                val = getattr(val, part, None)
        return val

    def child(self, extra: dict[str, Any]) -> "TemplateContext":
        """Return a new child context with extra variables."""
        merged = {**self._vars, **extra}
        return TemplateContext(merged)

    def eval_condition(self, expr: str) -> bool:
        """Evaluate a simple boolean expression."""
        expr = expr.strip()
        # Handle 'not expr'
        if expr.startswith("not "):
            return not self.eval_condition(expr[4:])
        # Handle 'a and b', 'a or b'
        for op in (" and ", " or "):
            if op in expr:
                idx = expr.index(op)
                left = self.eval_condition(expr[:idx])
                right = self.eval_condition(expr[idx + len(op):])
                return (left and right) if op.strip() == "and" else (left or right)
        # Handle comparisons
        for op in ("==", "!=", ">=", "<=", ">", "<", " in ", " not in "):
            if op in expr:
                parts = expr.split(op, 1)
                left_val = self._eval_value(parts[0].strip())
                right_val = self._eval_value(parts[1].strip())
                if op == "==":
                    return left_val == right_val
                if op == "!=":
                    return left_val != right_val
                if op == ">=":
                    return left_val >= right_val
                if op == "<=":
                    return left_val <= right_val
                if op == ">":
                    return left_val > right_val
                if op == "<":
                    return left_val < right_val
                if op == " in ":
                    return left_val in right_val
                if op == " not in ":
                    return left_val not in right_val
        # Simple truthy check
        val = self._eval_value(expr)
        return bool(val)

    def _eval_value(self, expr: str) -> Any:
        expr = expr.strip()
        if expr.startswith('"') and expr.endswith('"'):
            return expr[1:-1]
        if expr.startswith("'") and expr.endswith("'"):
            return expr[1:-1]
        if expr == "True":
            return True
        if expr == "False":
            return False
        if expr == "None":
            return None
        try:
            return int(expr)
        except ValueError:
            pass
        try:
            return float(expr)
        except ValueError:
            pass
        return self.resolve(expr)


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------

_BUILTIN_FILTERS: dict[str, Any] = {
    "upper": str.upper,
    "lower": str.lower,
    "title": str.title,
    "strip": str.strip,
    "len": len,
    "int": int,
    "float": float,
    "str": str,
    "bool": bool,
    "list": list,
    "sorted": sorted,
    "reversed": lambda x: list(reversed(list(x))),
    "join": lambda x, sep="": sep.join(str(i) for i in x),
    "first": lambda x: next(iter(x), None),
    "last": lambda x: (list(x) or [None])[-1],
    "default": lambda x, d="": x if x is not None else d,
    "truncate": lambda x, n=50: str(x)[:n] + ("..." if len(str(x)) > n else ""),
    "replace": lambda x, old="", new="": str(x).replace(old, new),
    "abs": abs,
    "round": round,
}


def _apply_filter(value: Any, filter_expr: str) -> Any:
    """Apply a filter expression like 'upper' or 'default("n/a")'."""
    filter_expr = filter_expr.strip()
    # Check for filter with arguments: filter_name(args...)
    m = re.match(r'^(\w+)\((.+)\)$', filter_expr)
    if m:
        fname = m.group(1)
        arg_str = m.group(2).strip()
        # Simple arg parsing: single string or int
        if (arg_str.startswith('"') and arg_str.endswith('"')) or \
           (arg_str.startswith("'") and arg_str.endswith("'")):
            arg = arg_str[1:-1]
        else:
            try:
                arg = int(arg_str)
            except ValueError:
                try:
                    arg = float(arg_str)
                except ValueError:
                    arg = arg_str
        fn = _BUILTIN_FILTERS.get(fname)
        if fn:
            return fn(value, arg)
        return value

    fn = _BUILTIN_FILTERS.get(filter_expr)
    if fn:
        return fn(value)
    return value


# ---------------------------------------------------------------------------
# TemplateEngine
# ---------------------------------------------------------------------------

_VAR_RE = re.compile(r'\{\{(.+?)\}\}')
_TAG_RE = re.compile(r'\{%(.+?)%\}')
_COMMENT_RE = re.compile(r'\{#.+?#\}', re.DOTALL)


class TemplateEngine:
    """
    Lightweight template engine.

    Parameters
    ----------
    template_dir : str | Path | None
        Base directory for {% include %} lookups.
    strict : bool
        If True, raise TemplateError on undefined variables.
        If False (default), undefined variables render as empty string.
    """

    def __init__(
        self,
        template_dir: str | Path | None = None,
        strict: bool = False,
    ) -> None:
        self._template_dir = Path(template_dir) if template_dir else None
        self._strict = strict

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def render(self, template: str, context: dict[str, Any] | TemplateContext | None = None) -> str:
        """
        Render a template string with the given context.

        Parameters
        ----------
        template : str
            Template source.
        context : dict | TemplateContext | None
            Variables available in the template.
        """
        ctx = context if isinstance(context, TemplateContext) else TemplateContext(context or {})
        return self._render(template, ctx)

    def render_file(self, path: str | Path, context: dict[str, Any] | TemplateContext | None = None) -> str:
        """Render a template file."""
        p = Path(path)
        if not p.exists():
            raise TemplateNotFound(f"Template file not found: {path}")
        template = p.read_text(encoding="utf-8")
        return self.render(template, context)

    # ------------------------------------------------------------------
    # Core rendering
    # ------------------------------------------------------------------

    def _render(self, template: str, ctx: TemplateContext) -> str:
        # Remove comments
        template = _COMMENT_RE.sub("", template)

        # Process raw blocks
        raw_blocks: dict[str, str] = {}
        raw_counter = [0]

        def save_raw(m: re.Match) -> str:
            key = f"\x00RAW{raw_counter[0]}\x00"
            raw_blocks[key] = m.group(1)
            raw_counter[0] += 1
            return key

        template = re.sub(r'\{%\s*raw\s*%\}(.+?)\{%\s*endraw\s*%\}', save_raw, template, flags=re.DOTALL)

        # Process structural blocks (if/for/include) — leaves {{ vars }} intact
        result = self._process_block(template, ctx)

        # Substitute top-level variables first (raw placeholders are safe — not {{ }})
        result = self._substitute_vars(result, ctx)

        # Restore raw blocks AFTER var substitution so their content is untouched
        for key, val in raw_blocks.items():
            result = result.replace(key, val)

        return result

    def _substitute_vars(self, text: str, ctx: TemplateContext) -> str:
        def replace_var(m: re.Match) -> str:
            expr = m.group(1).strip()
            # Handle filters: {{ value | filter1 | filter2 }}
            parts = [p.strip() for p in expr.split("|")]
            val = ctx.resolve(parts[0])
            for f in parts[1:]:
                val = _apply_filter(val, f)
            if val is None:
                if self._strict:
                    raise TemplateError(f"Undefined variable: {parts[0]!r}")
                return ""
            return str(val)
        return _VAR_RE.sub(replace_var, text)

    def _process_block(self, template: str, ctx: TemplateContext) -> str:
        """Process if/for/include blocks recursively."""
        result_parts: list[str] = []
        pos = 0

        while pos < len(template):
            tag_match = _TAG_RE.search(template, pos)
            if not tag_match:
                result_parts.append(template[pos:])
                break

            # Text before the tag
            result_parts.append(template[pos:tag_match.start()])
            tag_content = tag_match.group(1).strip()
            pos = tag_match.end()

            if tag_content.startswith("if "):
                condition = tag_content[3:].strip()
                body, pos = self._find_block(template, pos, "if")
                rendered = self._handle_if(body, condition, ctx)
                result_parts.append(rendered)

            elif tag_content.startswith("for "):
                parts = tag_content[4:].split(" in ", 1)
                if len(parts) != 2:
                    raise TemplateError(f"Invalid for syntax: {tag_content!r}")
                var_name = parts[0].strip()
                iterable_expr = parts[1].strip()
                body, pos = self._find_block(template, pos, "for")
                rendered = self._handle_for(body, var_name, iterable_expr, ctx)
                result_parts.append(rendered)

            elif tag_content.startswith("include "):
                filename = tag_content[8:].strip().strip('"\'')
                rendered = self._handle_include(filename, ctx)
                result_parts.append(rendered)

            elif tag_content in ("else", "elif") or tag_content.startswith("elif "):
                # These are consumed by _handle_if; if we encounter them here, stop
                result_parts.append(f"{{% {tag_content} %}}")

            elif tag_content in ("endif", "endfor", "endblock"):
                # End markers consumed by block handlers
                break

        return "".join(result_parts)

    def _find_block(self, template: str, start: int, block_type: str) -> tuple[str, int]:
        """Find matching end tag and return (block_content, pos_after_end)."""
        end_tag = f"end{block_type}"
        depth = 1
        pos = start
        while pos < len(template):
            m = _TAG_RE.search(template, pos)
            if not m:
                raise TemplateError(f"Unclosed {{% {block_type} %}} block")
            tag = m.group(1).strip()
            if tag.startswith(block_type + " ") or tag == block_type:
                depth += 1
            elif tag == end_tag:
                depth -= 1
                if depth == 0:
                    return template[start:m.start()], m.end()
            pos = m.end()
        raise TemplateError(f"Unclosed {{% {block_type} %}} block")

    def _handle_if(self, body: str, condition: str, ctx: TemplateContext) -> str:
        """Handle if/elif/else chain."""
        # Split on {% else %} and {% elif ... %}, tracking nesting depth
        branches: list[tuple[str | None, str]] = [(condition, "")]
        current_body_start = 0
        pos = 0
        depth = 0  # nesting depth for if blocks inside body
        while pos < len(body):
            m = _TAG_RE.search(body, pos)
            if not m:
                break
            tag = m.group(1).strip()
            if tag.startswith("if ") or tag == "if":
                depth += 1
            elif tag == "endif":
                depth -= 1
            elif depth == 0 and tag == "else":
                # Top-level else: split branch
                last = branches[-1]
                branches[-1] = (last[0], last[1] + body[current_body_start:m.start()])
                branches.append((None, ""))
                current_body_start = m.end()
            elif depth == 0 and tag.startswith("elif "):
                last = branches[-1]
                branches[-1] = (last[0], last[1] + body[current_body_start:m.start()])
                new_cond = tag[5:].strip()
                branches.append((new_cond, ""))
                current_body_start = m.end()
            pos = m.end()

        # Append remaining body to last branch
        last = branches[-1]
        branches[-1] = (last[0], last[1] + body[current_body_start:])

        # Evaluate branches
        for cond, branch_body in branches:
            if cond is None or ctx.eval_condition(cond):
                block_result = self._process_block(branch_body, ctx)
                return self._substitute_vars(block_result, ctx)
        return ""

    def _handle_for(self, body: str, var_name: str, iterable_expr: str, ctx: TemplateContext) -> str:
        """Handle for loop."""
        iterable = ctx.resolve(iterable_expr)
        if iterable is None:
            if self._strict:
                raise TemplateError(f"Undefined iterable: {iterable_expr!r}")
            return ""

        parts: list[str] = []
        items = list(iterable)
        for i, item in enumerate(items):
            child_ctx = ctx.child({
                var_name: item,
                "loop": {
                    "index": i + 1,
                    "index0": i,
                    "first": i == 0,
                    "last": i == len(items) - 1,
                    "length": len(items),
                },
            })
            block_result = self._process_block(body, child_ctx)
            parts.append(self._substitute_vars(block_result, child_ctx))
        return "".join(parts)

    def _handle_include(self, filename: str, ctx: TemplateContext) -> str:
        """Handle {% include 'file.html' %}."""
        if self._template_dir is None:
            raise TemplateError("template_dir must be set to use {% include %}")
        path = self._template_dir / filename
        if not path.exists():
            raise TemplateNotFound(f"Included template not found: {filename}")
        content = path.read_text(encoding="utf-8")
        return self._render(content, ctx)
