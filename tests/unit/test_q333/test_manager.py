"""Tests for lidco.adr.manager — ADRManager, ADR, ADRTemplate."""

from __future__ import annotations

import unittest

from lidco.adr.manager import ADR, ADRManager, ADRStatus, ADRTemplate


class TestADR(unittest.TestCase):
    """Tests for the ADR dataclass."""

    def test_defaults(self) -> None:
        adr = ADR(number=1, title="Use PostgreSQL")
        self.assertEqual(adr.number, 1)
        self.assertEqual(adr.title, "Use PostgreSQL")
        self.assertEqual(adr.status, ADRStatus.PROPOSED)
        self.assertTrue(adr.date)  # auto-filled
        self.assertIsNone(adr.superseded_by)

    def test_to_dict_roundtrip(self) -> None:
        adr = ADR(
            number=3, title="Use REST", status=ADRStatus.ACCEPTED,
            context="Need API", decision="Use REST", consequences="Standard",
            authors=["Alice"], tags=["api"],
        )
        d = adr.to_dict()
        self.assertEqual(d["number"], 3)
        self.assertEqual(d["status"], "accepted")
        restored = ADR.from_dict(d)
        self.assertEqual(restored.title, "Use REST")
        self.assertEqual(restored.status, ADRStatus.ACCEPTED)

    def test_from_dict_defaults(self) -> None:
        adr = ADR.from_dict({"number": 1, "title": "T"})
        self.assertEqual(adr.status, ADRStatus.PROPOSED)

    def test_to_markdown(self) -> None:
        adr = ADR(number=1, title="Use Python", context="Need lang", decision="Python", consequences="Good ecosystem")
        md = adr.to_markdown()
        self.assertIn("# ADR-0001: Use Python", md)
        self.assertIn("## Context", md)
        self.assertIn("Need lang", md)
        self.assertIn("## Decision", md)

    def test_to_markdown_superseded(self) -> None:
        adr = ADR(number=1, title="T", superseded_by=2)
        md = adr.to_markdown()
        self.assertIn("**Superseded by:** ADR-0002", md)

    def test_to_markdown_references(self) -> None:
        adr = ADR(number=1, title="T", references=["RFC-123", "ADR-0005"])
        md = adr.to_markdown()
        self.assertIn("## References", md)
        self.assertIn("- RFC-123", md)


class TestADRTemplate(unittest.TestCase):
    """Tests for ADRTemplate."""

    def test_render(self) -> None:
        tmpl = ADRTemplate(name="test")
        adr = ADR(number=1, title="Use Docker", context="Containers needed", decision="Docker", consequences="Infra dep")
        rendered = tmpl.render(adr)
        self.assertIn("ADR-0001", rendered)
        self.assertIn("Use Docker", rendered)
        self.assertIn("Containers needed", rendered)

    def test_custom_template(self) -> None:
        tmpl = ADRTemplate(name="minimal", content="# {number} - {title}\n{decision}\n")
        adr = ADR(number=5, title="Go", decision="Use Go")
        rendered = tmpl.render(adr)
        self.assertIn("0005", rendered)
        self.assertIn("Use Go", rendered)


class TestADRManager(unittest.TestCase):
    """Tests for ADRManager."""

    def setUp(self) -> None:
        self.mgr = ADRManager()

    def test_create(self) -> None:
        adr = self.mgr.create("Use PostgreSQL", context="Need DB", decision="PG")
        self.assertEqual(adr.number, 1)
        self.assertEqual(adr.title, "Use PostgreSQL")
        self.assertEqual(self.mgr.count, 1)

    def test_sequential_numbers(self) -> None:
        self.mgr.create("First")
        self.mgr.create("Second")
        self.assertEqual(self.mgr.next_number, 3)
        self.assertEqual(self.mgr.count, 2)

    def test_create_empty_title_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.mgr.create("")

    def test_get(self) -> None:
        self.mgr.create("First")
        adr = self.mgr.get(1)
        self.assertIsNotNone(adr)
        self.assertEqual(adr.title, "First")
        self.assertIsNone(self.mgr.get(999))

    def test_list_all(self) -> None:
        self.mgr.create("A")
        self.mgr.create("B")
        all_adrs = self.mgr.list_all()
        self.assertEqual(len(all_adrs), 2)
        self.assertEqual(all_adrs[0].number, 1)

    def test_list_by_status(self) -> None:
        self.mgr.create("A")
        self.mgr.create("B")
        self.mgr.update_status(1, ADRStatus.ACCEPTED)
        accepted = self.mgr.list_by_status(ADRStatus.ACCEPTED)
        self.assertEqual(len(accepted), 1)
        self.assertEqual(accepted[0].number, 1)

    def test_update_status(self) -> None:
        self.mgr.create("T")
        updated = self.mgr.update_status(1, ADRStatus.ACCEPTED)
        self.assertEqual(updated.status, ADRStatus.ACCEPTED)

    def test_update_status_not_found(self) -> None:
        with self.assertRaises(KeyError):
            self.mgr.update_status(99, ADRStatus.ACCEPTED)

    def test_supersede(self) -> None:
        self.mgr.create("Old")
        self.mgr.create("New")
        old = self.mgr.supersede(1, 2)
        self.assertEqual(old.status, ADRStatus.SUPERSEDED)
        self.assertEqual(old.superseded_by, 2)

    def test_supersede_not_found(self) -> None:
        self.mgr.create("Only")
        with self.assertRaises(KeyError):
            self.mgr.supersede(1, 99)

    def test_remove(self) -> None:
        self.mgr.create("T")
        removed = self.mgr.remove(1)
        self.assertEqual(removed.title, "T")
        self.assertEqual(self.mgr.count, 0)

    def test_remove_not_found(self) -> None:
        with self.assertRaises(KeyError):
            self.mgr.remove(99)

    def test_register_template(self) -> None:
        t = ADRTemplate(name="custom", content="# {number} {title}\n")
        self.mgr.register_template(t)
        self.assertIn("custom", self.mgr.list_templates())
        self.assertIsNotNone(self.mgr.get_template("custom"))

    def test_export_markdown(self) -> None:
        self.mgr.create("T", context="C", decision="D")
        md = self.mgr.export_markdown(1)
        self.assertIn("ADR-0001", md)

    def test_export_markdown_not_found(self) -> None:
        with self.assertRaises(KeyError):
            self.mgr.export_markdown(99)

    def test_export_all_markdown(self) -> None:
        self.mgr.create("A")
        self.mgr.create("B")
        all_md = self.mgr.export_all_markdown()
        self.assertEqual(len(all_md), 2)
        self.assertIn(1, all_md)
        self.assertIn(2, all_md)

    def test_base_dir(self) -> None:
        mgr = ADRManager(base_dir="/tmp/adrs")
        self.assertEqual(mgr.base_dir, "/tmp/adrs")

    def test_create_with_tags_and_authors(self) -> None:
        adr = self.mgr.create("T", authors=["Alice", "Bob"], tags=["api", "rest"])
        self.assertEqual(adr.authors, ["Alice", "Bob"])
        self.assertEqual(adr.tags, ["api", "rest"])


if __name__ == "__main__":
    unittest.main()
