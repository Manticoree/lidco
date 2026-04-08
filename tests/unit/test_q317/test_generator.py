"""Tests for lidco.e2e_intel.generator — E2ETestGenerator."""

from __future__ import annotations

import unittest

from lidco.e2e_intel.generator import (
    Assertion,
    AssertionType,
    DataSetup,
    E2ETestGenerator,
    Framework,
    GeneratedTest,
    GenerationResult,
    PageObject,
    TestStep,
)


class TestFrameworkEnum(unittest.TestCase):
    def test_values(self) -> None:
        self.assertEqual(Framework.PLAYWRIGHT.value, "playwright")
        self.assertEqual(Framework.CYPRESS.value, "cypress")


class TestAssertionTypeEnum(unittest.TestCase):
    def test_values(self) -> None:
        self.assertEqual(AssertionType.VISIBLE.value, "visible")
        self.assertEqual(AssertionType.TEXT_CONTENT.value, "text_content")
        self.assertEqual(AssertionType.URL.value, "url")
        self.assertEqual(AssertionType.COUNT.value, "count")
        self.assertEqual(AssertionType.ATTRIBUTE.value, "attribute")


class TestPageObject(unittest.TestCase):
    def test_frozen(self) -> None:
        po = PageObject(name="LoginPage", selectors=(("btn", "#login"),))
        with self.assertRaises(AttributeError):
            po.name = "x"  # type: ignore[misc]


class TestTestStep(unittest.TestCase):
    def test_frozen(self) -> None:
        s = TestStep(action="click", selector="#btn")
        with self.assertRaises(AttributeError):
            s.action = "fill"  # type: ignore[misc]


class TestAssertion(unittest.TestCase):
    def test_frozen(self) -> None:
        a = Assertion(assertion_type=AssertionType.VISIBLE, selector="#el")
        with self.assertRaises(AttributeError):
            a.selector = "x"  # type: ignore[misc]


class TestDataSetup(unittest.TestCase):
    def test_frozen(self) -> None:
        ds = DataSetup(name="seed_users", fixture_type="api")
        self.assertEqual(ds.name, "seed_users")
        self.assertEqual(ds.fixture_type, "api")


class TestE2ETestGenerator(unittest.TestCase):
    def test_default_framework(self) -> None:
        gen = E2ETestGenerator()
        self.assertEqual(gen.framework, Framework.PLAYWRIGHT)

    def test_custom_framework(self) -> None:
        gen = E2ETestGenerator(framework=Framework.CYPRESS)
        self.assertEqual(gen.framework, Framework.CYPRESS)

    def test_base_url(self) -> None:
        gen = E2ETestGenerator(base_url="http://example.com")
        self.assertEqual(gen.base_url, "http://example.com")

    def test_generate_page_object(self) -> None:
        gen = E2ETestGenerator()
        po = gen.generate_page_object(
            "LoginPage",
            {"username": "#user", "password": "#pass"},
            url_pattern="/login",
        )
        self.assertEqual(po.name, "LoginPage")
        self.assertEqual(po.url_pattern, "/login")
        self.assertEqual(len(po.selectors), 2)

    def test_generate_playwright_test(self) -> None:
        gen = E2ETestGenerator(framework=Framework.PLAYWRIGHT)
        test = gen.generate_test(
            name="login test",
            steps=[
                TestStep(action="navigate", value="http://localhost:3000"),
                TestStep(action="fill", selector="#user", value="admin"),
                TestStep(action="click", selector="#login"),
            ],
            assertions=[
                Assertion(assertion_type=AssertionType.VISIBLE, selector="#dashboard"),
                Assertion(
                    assertion_type=AssertionType.TEXT_CONTENT,
                    selector="#welcome",
                    expected="Hello",
                ),
            ],
        )
        self.assertEqual(test.name, "login test")
        self.assertEqual(test.framework, Framework.PLAYWRIGHT)
        self.assertIn("page.goto", test.code)
        self.assertIn('fill("admin")', test.code)
        self.assertIn("to_be_visible", test.code)
        self.assertIn("to_have_text", test.code)
        self.assertIn("def test_login_test", test.code)

    def test_generate_cypress_test(self) -> None:
        gen = E2ETestGenerator(framework=Framework.CYPRESS)
        test = gen.generate_test(
            name="search flow",
            steps=[
                TestStep(action="navigate", value="/search"),
                TestStep(action="fill", selector="#q", value="hello"),
                TestStep(action="click", selector="#go"),
            ],
            assertions=[
                Assertion(
                    assertion_type=AssertionType.VISIBLE, selector="#results"
                ),
                Assertion(
                    assertion_type=AssertionType.URL,
                    selector="",
                    expected="/search",
                ),
            ],
        )
        self.assertIn("cy.visit", test.code)
        self.assertIn("cy.get", test.code)
        self.assertIn('should("be.visible")', test.code)
        self.assertIn('should("include"', test.code)

    def test_generate_with_page_objects(self) -> None:
        gen = E2ETestGenerator()
        po = gen.generate_page_object("LoginPage", {"btn": "#login"})
        test = gen.generate_test(
            name="with po",
            steps=[TestStep(action="click", selector="#login")],
            assertions=[],
            page_objects=[po],
        )
        self.assertIn("class LoginPage", test.code)
        self.assertEqual(len(test.page_objects), 1)

    def test_generate_with_data_setup(self) -> None:
        gen = E2ETestGenerator()
        ds = DataSetup(name="seed_users", fixture_type="api", payload="{}")
        test = gen.generate_test(
            name="ds test",
            steps=[],
            assertions=[],
            data_setup=[ds],
        )
        self.assertEqual(len(test.data_setup), 1)
        self.assertIn("Setup: seed_users", test.code)

    def test_generate_wait_step(self) -> None:
        gen = E2ETestGenerator()
        test = gen.generate_test(
            name="wait",
            steps=[TestStep(action="wait", value="2000")],
            assertions=[],
        )
        self.assertIn("wait_for_timeout(2000)", test.code)

    def test_generate_url_assertion_playwright(self) -> None:
        gen = E2ETestGenerator()
        test = gen.generate_test(
            name="url check",
            steps=[],
            assertions=[
                Assertion(assertion_type=AssertionType.URL, selector="", expected="/dash"),
            ],
        )
        self.assertIn("to_have_url", test.code)

    def test_generate_count_assertion_playwright(self) -> None:
        gen = E2ETestGenerator()
        test = gen.generate_test(
            name="count check",
            steps=[],
            assertions=[
                Assertion(
                    assertion_type=AssertionType.COUNT,
                    selector=".item",
                    expected="5",
                ),
            ],
        )
        self.assertIn("to_have_count(5)", test.code)

    def test_generate_batch(self) -> None:
        gen = E2ETestGenerator()
        result = gen.generate_batch([
            ("t1", [TestStep(action="click", selector="#a")], []),
            (
                "t2",
                [TestStep(action="navigate", value="/")],
                [Assertion(assertion_type=AssertionType.VISIBLE, selector="#x")],
            ),
        ])
        self.assertIsInstance(result, GenerationResult)
        self.assertEqual(len(result.tests), 2)
        self.assertEqual(result.total_steps, 2)
        self.assertEqual(result.total_assertions, 1)

    def test_generated_test_frozen(self) -> None:
        gen = E2ETestGenerator()
        test = gen.generate_test(name="f", steps=[], assertions=[])
        with self.assertRaises(AttributeError):
            test.name = "x"  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
