"""Tests for EditTransaction (Q146 task 862)."""
from __future__ import annotations

import unittest

from lidco.editing.edit_transaction import EditOp, EditTransaction


class TestEditOp(unittest.TestCase):
    def test_create_op(self):
        op = EditOp("a.py", "create", None, "content", 1.0)
        self.assertEqual(op.file_path, "a.py")
        self.assertEqual(op.op_type, "create")
        self.assertIsNone(op.old_content)
        self.assertEqual(op.new_content, "content")

    def test_modify_op(self):
        op = EditOp("b.py", "modify", "old", "new", 2.0)
        self.assertEqual(op.old_content, "old")
        self.assertEqual(op.new_content, "new")

    def test_delete_op(self):
        op = EditOp("c.py", "delete", "old", None, 3.0)
        self.assertEqual(op.op_type, "delete")
        self.assertIsNone(op.new_content)

    def test_timestamp_auto(self):
        op = EditOp("x.py", "modify", "a", "b")
        self.assertGreater(op.timestamp, 0)


class TestEditTransaction(unittest.TestCase):
    def test_empty_transaction(self):
        tx = EditTransaction()
        self.assertTrue(tx.is_empty)
        self.assertEqual(tx.operations, [])
        self.assertEqual(tx.label, "")

    def test_label(self):
        tx = EditTransaction(label="refactor")
        self.assertEqual(tx.label, "refactor")

    def test_add_single(self):
        tx = EditTransaction()
        tx.add("a.py", "modify", "old", "new")
        self.assertFalse(tx.is_empty)
        self.assertEqual(len(tx.operations), 1)

    def test_add_multiple(self):
        tx = EditTransaction()
        tx.add("a.py", "modify", "old", "new")
        tx.add("b.py", "create", None, "content")
        tx.add("c.py", "delete", "content", None)
        self.assertEqual(len(tx.operations), 3)

    def test_operations_returns_copy(self):
        tx = EditTransaction()
        tx.add("a.py", "modify", "a", "b")
        ops = tx.operations
        ops.clear()
        self.assertEqual(len(tx.operations), 1)

    def test_files_affected_dedup(self):
        tx = EditTransaction()
        tx.add("a.py", "modify", "a", "b")
        tx.add("a.py", "modify", "b", "c")
        tx.add("b.py", "create", None, "x")
        self.assertEqual(tx.files_affected(), ["a.py", "b.py"])

    def test_files_affected_preserves_order(self):
        tx = EditTransaction()
        tx.add("z.py", "create", None, "z")
        tx.add("a.py", "create", None, "a")
        self.assertEqual(tx.files_affected(), ["z.py", "a.py"])

    def test_summary_empty(self):
        tx = EditTransaction()
        self.assertEqual(tx.summary(), "no changes")

    def test_summary_single_modify(self):
        tx = EditTransaction()
        tx.add("a.py", "modify", "a", "b")
        self.assertEqual(tx.summary(), "1 file modified")

    def test_summary_multiple_types(self):
        tx = EditTransaction()
        tx.add("a.py", "modify", "a", "b")
        tx.add("b.py", "modify", "c", "d")
        tx.add("c.py", "modify", "e", "f")
        tx.add("d.py", "create", None, "x")
        s = tx.summary()
        self.assertIn("3 files modified", s)
        self.assertIn("1 file created", s)

    def test_summary_delete(self):
        tx = EditTransaction()
        tx.add("a.py", "delete", "x", None)
        tx.add("b.py", "delete", "y", None)
        self.assertIn("2 files deleted", tx.summary())

    def test_rollback_modify(self):
        tx = EditTransaction()
        tx.add("a.py", "modify", "old", "new")
        rb = tx.rollback_ops()
        self.assertEqual(len(rb), 1)
        self.assertEqual(rb[0].op_type, "modify")
        self.assertEqual(rb[0].old_content, "new")
        self.assertEqual(rb[0].new_content, "old")

    def test_rollback_create_becomes_delete(self):
        tx = EditTransaction()
        tx.add("a.py", "create", None, "content")
        rb = tx.rollback_ops()
        self.assertEqual(rb[0].op_type, "delete")
        self.assertEqual(rb[0].old_content, "content")

    def test_rollback_delete_becomes_create(self):
        tx = EditTransaction()
        tx.add("a.py", "delete", "content", None)
        rb = tx.rollback_ops()
        self.assertEqual(rb[0].op_type, "create")
        self.assertEqual(rb[0].new_content, "content")

    def test_rollback_reversed_order(self):
        tx = EditTransaction()
        tx.add("a.py", "modify", "a1", "a2")
        tx.add("b.py", "modify", "b1", "b2")
        rb = tx.rollback_ops()
        self.assertEqual(rb[0].file_path, "b.py")
        self.assertEqual(rb[1].file_path, "a.py")

    def test_rollback_empty(self):
        tx = EditTransaction()
        self.assertEqual(tx.rollback_ops(), [])

    def test_timestamp_set(self):
        tx = EditTransaction()
        self.assertGreater(tx.timestamp, 0)

    def test_files_affected_empty(self):
        tx = EditTransaction()
        self.assertEqual(tx.files_affected(), [])


if __name__ == "__main__":
    unittest.main()
