"""CRUDGenerator — generate model, routes, and test boilerplate."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ModelDef:
    """Definition of a data model for CRUD generation."""

    name: str
    fields: list[dict[str, str]] = field(default_factory=list)


class CRUDGenerator:
    """Generate CRUD boilerplate for a given :class:`ModelDef`."""

    def generate(self, model: ModelDef, style: str = "rest") -> dict[str, str]:
        """Return filepath->content dict for model, routes, and tests.

        *style* is currently ``"rest"`` (default).
        """
        lower = model.name.lower()
        return {
            f"{lower}/model.py": self.generate_model(model),
            f"{lower}/routes.py": self.generate_routes(model),
            f"tests/test_{lower}.py": self.generate_tests(model),
        }

    def generate_model(self, model: ModelDef) -> str:
        """Generate a Python dataclass model."""
        lines: list[str] = [
            "from __future__ import annotations",
            "",
            "from dataclasses import dataclass, field",
            "",
            "",
            f"@dataclass(frozen=True)",
            f"class {model.name}:",
            f'    """{model.name} data model."""',
            "",
        ]
        if not model.fields:
            lines.append("    pass")
        else:
            for fld in model.fields:
                name = fld.get("name", "unknown")
                ftype = fld.get("type", "str")
                lines.append(f"    {name}: {ftype}")
        lines.append("")
        return "\n".join(lines)

    def generate_routes(self, model: ModelDef) -> str:
        """Generate REST-style route stubs."""
        lower = model.name.lower()
        upper = model.name
        field_names = [f.get("name", "unknown") for f in model.fields]
        field_dict = ", ".join(f'"{n}": item.{n}' for n in field_names) if field_names else ""

        lines: list[str] = [
            "from __future__ import annotations",
            "",
            f"from {lower}.model import {upper}",
            "",
            f"_store: dict[str, {upper}] = {{}}",
            "",
            "",
            f"def list_{lower}s() -> list[dict]:",
            f'    """List all {lower}s."""',
            f"    return [{{\"id\": k, {field_dict}}} for k, item in _store.items()]"
            if field_dict
            else f'    return [{{"id": k}} for k in _store]',
            "",
            "",
            f"def get_{lower}(id_: str) -> dict | None:",
            f'    """Get a {lower} by id."""',
            f"    item = _store.get(id_)",
            f"    if item is None:",
            f"        return None",
            f'    return {{"id": id_, {field_dict}}}'
            if field_dict
            else f'    return {{"id": id_}}',
            "",
            "",
            f"def create_{lower}(data: dict) -> dict:",
            f'    """Create a new {lower}."""',
            f"    import uuid",
            f'    id_ = str(uuid.uuid4())',
        ]
        # Build constructor call
        if field_names:
            ctor_args = ", ".join(f'{n}=data.get("{n}", "")' for n in field_names)
            lines.append(f"    item = {upper}({ctor_args})")
        else:
            lines.append(f"    item = {upper}()")
        lines += [
            f"    _store[id_] = item",
            f'    return {{"id": id_}}',
            "",
            "",
            f"def delete_{lower}(id_: str) -> bool:",
            f'    """Delete a {lower} by id."""',
            f"    if id_ in _store:",
            f"        del _store[id_]",  # route code can mutate its own store
            f"        return True",
            f"    return False",
            "",
        ]
        return "\n".join(lines)

    def generate_tests(self, model: ModelDef) -> str:
        """Generate basic test stubs."""
        lower = model.name.lower()
        lines: list[str] = [
            "from __future__ import annotations",
            "",
            "",
            f"def test_create_{lower}() -> None:",
            f'    """Placeholder test for {model.name} creation."""',
            f"    assert True",
            "",
            "",
            f"def test_list_{lower}s() -> None:",
            f'    """Placeholder test for listing {model.name}s."""',
            f"    assert True",
            "",
            "",
            f"def test_delete_{lower}() -> None:",
            f'    """Placeholder test for deleting {model.name}."""',
            f"    assert True",
            "",
        ]
        return "\n".join(lines)
