"""
E2E Test Generator — Generate E2E test code for Playwright/Cypress,
including page objects, assertions, and data setup.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Sequence


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


class Framework(Enum):
    """Supported E2E frameworks."""

    PLAYWRIGHT = "playwright"
    CYPRESS = "cypress"


class AssertionType(Enum):
    """Types of assertions to generate."""

    VISIBLE = "visible"
    TEXT_CONTENT = "text_content"
    URL = "url"
    COUNT = "count"
    ATTRIBUTE = "attribute"


@dataclass(frozen=True)
class PageObject:
    """A generated page object."""

    name: str
    selectors: tuple[tuple[str, str], ...]  # (name, selector) pairs
    url_pattern: str = ""


@dataclass(frozen=True)
class Assertion:
    """A single assertion in a test."""

    assertion_type: AssertionType
    selector: str
    expected: str = ""


@dataclass(frozen=True)
class TestStep:
    """A single step in a generated E2E test."""

    action: str  # click, fill, navigate, wait
    selector: str = ""
    value: str = ""
    description: str = ""


@dataclass(frozen=True)
class DataSetup:
    """Data setup required before a test."""

    name: str
    fixture_type: str  # api, seed, fixture
    payload: str = ""


@dataclass(frozen=True)
class GeneratedTest:
    """A complete generated E2E test."""

    name: str
    framework: Framework
    steps: tuple[TestStep, ...]
    assertions: tuple[Assertion, ...]
    page_objects: tuple[PageObject, ...]
    data_setup: tuple[DataSetup, ...] = ()
    code: str = ""


@dataclass(frozen=True)
class GenerationResult:
    """Result of an E2E test generation run."""

    tests: tuple[GeneratedTest, ...]
    total_steps: int
    total_assertions: int


# ---------------------------------------------------------------------------
# Code emitters
# ---------------------------------------------------------------------------


def _emit_playwright(test: GeneratedTest) -> str:
    """Emit Playwright Python test code."""
    lines: list[str] = [
        "import re",
        "from playwright.sync_api import Page, expect",
        "",
        "",
    ]

    # Page objects
    for po in test.page_objects:
        lines.append(f"class {po.name}:")
        lines.append(f'    """Page object for {po.name}."""')
        lines.append("")
        lines.append("    def __init__(self, page: Page) -> None:")
        lines.append("        self.page = page")
        for sel_name, sel_val in po.selectors:
            lines.append(f'        self.{sel_name} = page.locator("{sel_val}")')
        lines.append("")
        lines.append("")

    # Test function
    safe_name = test.name.replace(" ", "_").replace("-", "_").lower()
    lines.append(f"def test_{safe_name}(page: Page) -> None:")
    lines.append(f'    """E2E test: {test.name}."""')

    # Data setup
    for ds in test.data_setup:
        lines.append(f"    # Setup: {ds.name} ({ds.fixture_type})")

    # Steps
    for step in test.steps:
        if step.action == "navigate":
            lines.append(f'    page.goto("{step.value}")')
        elif step.action == "click":
            lines.append(f'    page.locator("{step.selector}").click()')
        elif step.action == "fill":
            lines.append(
                f'    page.locator("{step.selector}").fill("{step.value}")'
            )
        elif step.action == "wait":
            lines.append(f"    page.wait_for_timeout({step.value or '1000'})")
        else:
            lines.append(f"    # {step.action}: {step.description}")

    # Assertions
    for a in test.assertions:
        if a.assertion_type == AssertionType.VISIBLE:
            lines.append(
                f'    expect(page.locator("{a.selector}")).to_be_visible()'
            )
        elif a.assertion_type == AssertionType.TEXT_CONTENT:
            lines.append(
                f'    expect(page.locator("{a.selector}")).to_have_text("{a.expected}")'
            )
        elif a.assertion_type == AssertionType.URL:
            lines.append(
                f'    expect(page).to_have_url(re.compile(r"{a.expected}"))'
            )
        elif a.assertion_type == AssertionType.COUNT:
            lines.append(
                f'    expect(page.locator("{a.selector}")).to_have_count({a.expected})'
            )

    lines.append("")
    return "\n".join(lines)


def _emit_cypress(test: GeneratedTest) -> str:
    """Emit Cypress JavaScript test code."""
    lines: list[str] = []
    safe_name = test.name.replace(" ", "_").replace("-", "_").lower()

    lines.append(f'describe("{test.name}", () => {{')
    lines.append(f'  it("should complete {safe_name}", () => {{')

    for step in test.steps:
        if step.action == "navigate":
            lines.append(f'    cy.visit("{step.value}");')
        elif step.action == "click":
            lines.append(f'    cy.get("{step.selector}").click();')
        elif step.action == "fill":
            lines.append(
                f'    cy.get("{step.selector}").type("{step.value}");'
            )
        elif step.action == "wait":
            lines.append(f"    cy.wait({step.value or '1000'});")

    for a in test.assertions:
        if a.assertion_type == AssertionType.VISIBLE:
            lines.append(f'    cy.get("{a.selector}").should("be.visible");')
        elif a.assertion_type == AssertionType.TEXT_CONTENT:
            lines.append(
                f'    cy.get("{a.selector}").should("have.text", "{a.expected}");'
            )
        elif a.assertion_type == AssertionType.URL:
            lines.append(f'    cy.url().should("include", "{a.expected}");')

    lines.append("  });")
    lines.append("});")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------


class E2ETestGenerator:
    """Generate E2E test code from specifications."""

    def __init__(
        self,
        *,
        framework: Framework = Framework.PLAYWRIGHT,
        base_url: str = "http://localhost:3000",
    ) -> None:
        self._framework = framework
        self._base_url = base_url

    @property
    def framework(self) -> Framework:
        return self._framework

    @property
    def base_url(self) -> str:
        return self._base_url

    def generate_page_object(
        self,
        name: str,
        selectors: dict[str, str],
        *,
        url_pattern: str = "",
    ) -> PageObject:
        """Create a page object definition."""
        return PageObject(
            name=name,
            selectors=tuple(sorted(selectors.items())),
            url_pattern=url_pattern,
        )

    def generate_test(
        self,
        name: str,
        steps: Sequence[TestStep],
        assertions: Sequence[Assertion],
        *,
        page_objects: Sequence[PageObject] = (),
        data_setup: Sequence[DataSetup] = (),
    ) -> GeneratedTest:
        """Generate a single E2E test with code."""
        test = GeneratedTest(
            name=name,
            framework=self._framework,
            steps=tuple(steps),
            assertions=tuple(assertions),
            page_objects=tuple(page_objects),
            data_setup=tuple(data_setup),
        )

        if self._framework == Framework.PLAYWRIGHT:
            code = _emit_playwright(test)
        else:
            code = _emit_cypress(test)

        # Return new frozen instance with code populated
        return GeneratedTest(
            name=test.name,
            framework=test.framework,
            steps=test.steps,
            assertions=test.assertions,
            page_objects=test.page_objects,
            data_setup=test.data_setup,
            code=code,
        )

    def generate_batch(
        self,
        specs: Sequence[
            tuple[str, Sequence[TestStep], Sequence[Assertion]]
        ],
    ) -> GenerationResult:
        """Generate multiple tests at once."""
        tests: list[GeneratedTest] = []
        total_steps = 0
        total_assertions = 0
        for name, steps, assertions in specs:
            t = self.generate_test(name, steps, assertions)
            tests.append(t)
            total_steps += len(t.steps)
            total_assertions += len(t.assertions)

        return GenerationResult(
            tests=tuple(tests),
            total_steps=total_steps,
            total_assertions=total_assertions,
        )
