"""Tests for debate.personas."""
import unittest
from lidco.debate.personas import PersonaRegistry, Persona, OPTIMIST, PESSIMIST


class TestPersona(unittest.TestCase):

    def test_render_prompt(self):
        result = OPTIMIST.render_prompt("Use Python 4?")
        self.assertIn("Use Python 4?", result)
        self.assertNotIn("{{topic}}", result)

    def test_frozen(self):
        with self.assertRaises(AttributeError):
            OPTIMIST.name = "changed"

    def test_traits(self):
        self.assertIn("positive", OPTIMIST.traits)
        self.assertIn("cautious", PESSIMIST.traits)


class TestPersonaRegistry(unittest.TestCase):

    def setUp(self):
        self.reg = PersonaRegistry()

    def test_builtins_loaded(self):
        names = self.reg.names()
        self.assertIn("optimist", names)
        self.assertIn("pessimist", names)
        self.assertIn("pragmatist", names)
        self.assertIn("security", names)
        self.assertIn("performance", names)

    def test_register_custom(self):
        p = Persona(name="architect", description="Architecture focus", system_prompt="You are an architect.")
        self.reg.register(p)
        self.assertIsNotNone(self.reg.get("architect"))

    def test_get_unknown(self):
        self.assertIsNone(self.reg.get("nonexistent"))

    def test_remove(self):
        self.assertTrue(self.reg.remove("optimist"))
        self.assertIsNone(self.reg.get("optimist"))

    def test_remove_unknown(self):
        self.assertFalse(self.reg.remove("nonexistent"))

    def test_list_all(self):
        all_p = self.reg.list_all()
        self.assertEqual(len(all_p), 5)

    def test_builtin_names(self):
        names = self.reg.builtin_names()
        self.assertEqual(len(names), 5)


if __name__ == "__main__":
    unittest.main()
