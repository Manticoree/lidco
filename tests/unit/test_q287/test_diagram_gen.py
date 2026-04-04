"""Tests for lidco.multimodal.diagram_gen2."""
from __future__ import annotations

import unittest

from lidco.multimodal.diagram_gen2 import (
    CallInfo,
    ClassInfo,
    ComponentInfo,
    DiagramGenerator2,
)


class TestDiagramGenerator2(unittest.TestCase):
    def setUp(self):
        self.gen = DiagramGenerator2()

    # -- class_diagram ----------------------------------------------------

    def test_class_diagram_empty(self):
        result = self.gen.class_diagram([])
        self.assertEqual(result, "classDiagram")

    def test_class_diagram_single(self):
        classes = [ClassInfo(name="Foo", methods=["run"], attributes=["x"])]
        result = self.gen.class_diagram(classes)
        self.assertIn("classDiagram", result)
        self.assertIn("class Foo", result)
        self.assertIn("+x", result)
        self.assertIn("+run()", result)

    def test_class_diagram_inheritance(self):
        classes = [
            ClassInfo(name="Base", methods=["init"]),
            ClassInfo(name="Child", methods=["exec"], parent="Base"),
        ]
        result = self.gen.class_diagram(classes)
        self.assertIn("Base <|-- Child", result)

    def test_class_diagram_multiple_methods(self):
        classes = [ClassInfo(name="Svc", methods=["a", "b", "c"])]
        result = self.gen.class_diagram(classes)
        self.assertIn("+a()", result)
        self.assertIn("+b()", result)
        self.assertIn("+c()", result)

    # -- sequence_diagram -------------------------------------------------

    def test_sequence_diagram_empty(self):
        result = self.gen.sequence_diagram([])
        self.assertEqual(result, "sequenceDiagram")

    def test_sequence_diagram_basic(self):
        calls = [CallInfo(caller="A", callee="B", method="ping")]
        result = self.gen.sequence_diagram(calls)
        self.assertIn("sequenceDiagram", result)
        self.assertIn("A->>B: ping", result)

    def test_sequence_diagram_return(self):
        calls = [CallInfo(caller="A", callee="B", method="get", return_type="data")]
        result = self.gen.sequence_diagram(calls)
        self.assertIn("B-->>", result)
        self.assertIn("data", result)

    def test_sequence_diagram_multiple(self):
        calls = [
            CallInfo(caller="C", callee="S", method="req"),
            CallInfo(caller="S", callee="D", method="query"),
        ]
        result = self.gen.sequence_diagram(calls)
        self.assertIn("C->>S: req", result)
        self.assertIn("S->>D: query", result)

    # -- architecture_diagram ---------------------------------------------

    def test_arch_diagram_empty(self):
        result = self.gen.architecture_diagram([])
        self.assertEqual(result, "flowchart TD")

    def test_arch_diagram_single(self):
        comps = [ComponentInfo(name="API", kind="service", description="REST API")]
        result = self.gen.architecture_diagram(comps)
        self.assertIn("flowchart TD", result)
        self.assertIn("API", result)
        self.assertIn("REST API", result)

    def test_arch_diagram_dependency(self):
        comps = [
            ComponentInfo(name="Web", kind="gateway"),
            ComponentInfo(name="DB", kind="database", depends_on=["Web"]),
        ]
        result = self.gen.architecture_diagram(comps)
        self.assertIn("DB --> Web", result)

    def test_arch_diagram_shapes(self):
        comps = [
            ComponentInfo(name="Q", kind="queue", description="MQ"),
            ComponentInfo(name="E", kind="external", description="Third party"),
        ]
        result = self.gen.architecture_diagram(comps)
        self.assertIn("[[", result)  # queue shape
        self.assertIn("((", result)  # external shape


if __name__ == "__main__":
    unittest.main()
