"""Codegen Registry — register and apply code generation templates.

Stdlib only — no external deps.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class TemplateResult:
    """Result of applying a template."""
    name: str
    content: str
    template_type: str


class CodegenRegistry:
    """Registry of named code generation template functions."""

    def __init__(self) -> None:
        self._templates: dict[str, Callable] = {}

    def register(self, name: str, template_fn: Callable) -> None:
        """Register a template function under a name."""
        self._templates[name] = template_fn

    def get(self, name: str) -> Optional[Callable]:
        """Get a template function by name."""
        return self._templates.get(name)

    def list_templates(self) -> list[str]:
        """Return sorted list of registered template names."""
        return sorted(self._templates.keys())

    def apply(self, template_name: str, **kwargs) -> TemplateResult:
        """Apply a registered template with keyword arguments."""
        fn = self._templates.get(template_name)
        if fn is None:
            raise KeyError(f"Template '{template_name}' not registered")
        content = fn(**kwargs)
        return TemplateResult(name=template_name, content=content, template_type=template_name)

    @classmethod
    def with_defaults(cls) -> "CodegenRegistry":
        """Create a registry with class/test/module templates pre-registered."""
        from lidco.codegen.class_template import ClassTemplate, ClassConfig
        from lidco.codegen.test_template import TestTemplate, TestConfig
        from lidco.codegen.module_template import ModuleTemplate, ModuleConfig

        registry = cls()

        ct = ClassTemplate()
        tt = TestTemplate()
        mt = ModuleTemplate()

        def gen_class(**kwargs) -> str:
            config = ClassConfig(**kwargs)
            return ct.render(config)

        def gen_dataclass(**kwargs) -> str:
            config = ClassConfig(**kwargs)
            return ct.render_dataclass(config)

        def gen_abc(**kwargs) -> str:
            config = ClassConfig(**kwargs)
            return ct.render_abc(config)

        def gen_test(**kwargs) -> str:
            config = TestConfig(**kwargs)
            return tt.render(config)

        def gen_module(**kwargs) -> str:
            config = ModuleConfig(**kwargs)
            return mt.render(config)

        registry.register("class", gen_class)
        registry.register("dataclass", gen_dataclass)
        registry.register("abc", gen_abc)
        registry.register("test", gen_test)
        registry.register("module", gen_module)

        return registry
