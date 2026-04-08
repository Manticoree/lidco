"""Tests for lidco.iac.pulumi — PulumiGenerator, rendering, stack management."""

from __future__ import annotations

import unittest

from lidco.iac.pulumi import (
    PulumiGenerator,
    PulumiProgram,
    PulumiResource,
    PulumiStack,
    _camel,
    _py_dict,
    _ts_obj,
)


class TestHelpers(unittest.TestCase):
    def test_camel_simple(self) -> None:
        self.assertEqual(_camel("my-bucket"), "myBucket")

    def test_camel_no_dash(self) -> None:
        self.assertEqual(_camel("bucket"), "bucket")

    def test_camel_multi_dash(self) -> None:
        self.assertEqual(_camel("a-b-c"), "aBC")

    def test_py_dict(self) -> None:
        result = _py_dict({"key": "val"})
        self.assertIn('"key"', result)
        self.assertIn('"val"', result)

    def test_py_dict_bool(self) -> None:
        result = _py_dict({"flag": True})
        self.assertIn("True", result)

    def test_ts_obj(self) -> None:
        result = _ts_obj({"key": "val"})
        self.assertIn("key:", result)
        self.assertIn('"val"', result)

    def test_ts_obj_bool(self) -> None:
        result = _ts_obj({"flag": False})
        self.assertIn("false", result)

    def test_py_dict_list(self) -> None:
        result = _py_dict({"items": [1, 2]})
        self.assertIn("[1, 2]", result)

    def test_ts_obj_list(self) -> None:
        result = _ts_obj({"items": [1, 2]})
        self.assertIn("[1, 2]", result)


class TestPulumiResource(unittest.TestCase):
    def test_render_python(self) -> None:
        r = PulumiResource(
            name="my-bucket",
            resource_type="aws:s3:Bucket",
            properties={"acl": "private"},
        )
        out = r.render_python()
        self.assertIn("my_bucket", out)
        self.assertIn("aws:s3:Bucket", out)
        self.assertIn('"private"', out)

    def test_render_typescript(self) -> None:
        r = PulumiResource(
            name="my-bucket",
            resource_type="aws:s3:Bucket",
            properties={"acl": "private"},
        )
        out = r.render_typescript()
        self.assertIn("myBucket", out)
        self.assertIn("const", out)

    def test_render_no_props_python(self) -> None:
        r = PulumiResource(name="topic", resource_type="aws:sns:Topic")
        out = r.render_python()
        self.assertIn("{}", out)

    def test_render_no_props_typescript(self) -> None:
        r = PulumiResource(name="topic", resource_type="aws:sns:Topic")
        out = r.render_typescript()
        self.assertIn("{}", out)

    def test_frozen(self) -> None:
        r = PulumiResource(name="x", resource_type="aws:s3:Bucket")
        with self.assertRaises(AttributeError):
            r.name = "y"  # type: ignore[misc]


class TestPulumiStack(unittest.TestCase):
    def test_render_yaml(self) -> None:
        s = PulumiStack(name="dev", config={"aws:region": "us-east-1"})
        out = s.render_yaml()
        self.assertIn("config:", out)
        self.assertIn("aws:region: us-east-1", out)


class TestPulumiProgram(unittest.TestCase):
    def test_render_python(self) -> None:
        prog = PulumiProgram(
            project_name="test",
            language="python",
            resources=[PulumiResource("bucket", "aws:s3:Bucket")],
        )
        files = prog.render()
        self.assertIn("Pulumi.yaml", files)
        self.assertIn("__main__.py", files)
        self.assertIn("import pulumi_aws", files["__main__.py"])

    def test_render_typescript(self) -> None:
        prog = PulumiProgram(
            project_name="test",
            language="typescript",
            resources=[PulumiResource("bucket", "aws:s3:Bucket")],
        )
        files = prog.render()
        self.assertIn("index.ts", files)
        self.assertIn("@pulumi/aws", files["index.ts"])

    def test_stack_configs(self) -> None:
        prog = PulumiProgram(
            project_name="test",
            stacks=[PulumiStack("dev", {"aws:region": "us-east-1"})],
        )
        files = prog.render()
        self.assertIn("Pulumi.dev.yaml", files)

    def test_grouped_resources(self) -> None:
        prog = PulumiProgram(
            project_name="test",
            resources=[
                PulumiResource("a", "aws:s3:Bucket", group="storage"),
                PulumiResource("b", "aws:sns:Topic", group="messaging"),
                PulumiResource("c", "aws:s3:Object", group="storage"),
            ],
        )
        groups = prog.grouped_resources()
        self.assertIn("storage", groups)
        self.assertIn("messaging", groups)
        self.assertEqual(len(groups["storage"]), 2)

    def test_runtime_nodejs(self) -> None:
        prog = PulumiProgram(project_name="ts", language="typescript")
        files = prog.render()
        self.assertIn("runtime: nodejs", files["Pulumi.yaml"])

    def test_runtime_python(self) -> None:
        prog = PulumiProgram(project_name="py", language="python")
        files = prog.render()
        self.assertIn("runtime: python", files["Pulumi.yaml"])

    def test_groups_in_render_python(self) -> None:
        prog = PulumiProgram(
            project_name="test",
            language="python",
            resources=[
                PulumiResource("a", "aws:s3:Bucket", group="storage"),
            ],
        )
        files = prog.render()
        self.assertIn("# --- storage ---", files["__main__.py"])

    def test_groups_in_render_typescript(self) -> None:
        prog = PulumiProgram(
            project_name="test",
            language="typescript",
            resources=[
                PulumiResource("a", "aws:s3:Bucket", group="storage"),
            ],
        )
        files = prog.render()
        self.assertIn("// --- storage ---", files["index.ts"])


class TestPulumiGenerator(unittest.TestCase):
    def test_empty_generate(self) -> None:
        gen = PulumiGenerator()
        files = gen.generate()
        self.assertIn("Pulumi.yaml", files)

    def test_add_resource_immutable(self) -> None:
        gen1 = PulumiGenerator()
        gen2 = gen1.add_resource("bucket", "aws:s3:Bucket")
        self.assertIsNot(gen1, gen2)
        self.assertEqual(len(gen1.program.resources), 0)
        self.assertEqual(len(gen2.program.resources), 1)

    def test_add_stack(self) -> None:
        gen = PulumiGenerator().add_stack("prod", **{"aws:region": "eu-west-1"})
        files = gen.generate()
        self.assertIn("Pulumi.prod.yaml", files)

    def test_chained_build(self) -> None:
        gen = (
            PulumiGenerator(project_name="demo", language="typescript")
            .add_resource("bucket", "aws:s3:Bucket", group="storage")
            .add_resource("topic", "aws:sns:Topic", group="messaging")
            .add_stack("dev")
        )
        files = gen.generate()
        self.assertIn("index.ts", files)
        self.assertIn("Pulumi.dev.yaml", files)

    def test_language_preserved(self) -> None:
        gen = PulumiGenerator(language="typescript").add_resource("x", "aws:s3:Bucket")
        self.assertEqual(gen.program.language, "typescript")

    def test_project_name_preserved(self) -> None:
        gen = PulumiGenerator(project_name="myproj").add_stack("dev")
        self.assertEqual(gen.program.project_name, "myproj")


if __name__ == "__main__":
    unittest.main()
