"""Tests for lidco.iac.terraform — TerraformGenerator, dataclasses, rendering."""

from __future__ import annotations

import unittest

from lidco.iac.terraform import (
    StateConfig,
    TerraformConfig,
    TerraformGenerator,
    TerraformModule,
    TerraformOutput,
    TerraformProvider,
    TerraformResource,
    TerraformVariable,
    _tf_value,
)


class TestTfValue(unittest.TestCase):
    def test_string(self) -> None:
        self.assertEqual(_tf_value("hello"), '"hello"')

    def test_int(self) -> None:
        self.assertEqual(_tf_value(42), "42")

    def test_float(self) -> None:
        self.assertEqual(_tf_value(3.14), "3.14")

    def test_bool_true(self) -> None:
        self.assertEqual(_tf_value(True), "true")

    def test_bool_false(self) -> None:
        self.assertEqual(_tf_value(False), "false")

    def test_list(self) -> None:
        self.assertEqual(_tf_value([1, "a"]), '[1, "a"]')

    def test_dict(self) -> None:
        result = _tf_value({"k": "v"})
        self.assertIn("k = ", result)
        self.assertIn('"v"', result)


class TestTerraformVariable(unittest.TestCase):
    def test_render_minimal(self) -> None:
        v = TerraformVariable(name="region")
        out = v.render()
        self.assertIn('variable "region"', out)
        self.assertIn("type        = string", out)

    def test_render_full(self) -> None:
        v = TerraformVariable(
            name="db_pass",
            type="string",
            description="Database password",
            default="changeme",
            sensitive=True,
        )
        out = v.render()
        self.assertIn("sensitive   = true", out)
        self.assertIn("Database password", out)
        self.assertIn('"changeme"', out)

    def test_frozen(self) -> None:
        v = TerraformVariable(name="x")
        with self.assertRaises(AttributeError):
            v.name = "y"  # type: ignore[misc]


class TestTerraformOutput(unittest.TestCase):
    def test_render(self) -> None:
        o = TerraformOutput(name="vpc_id", value="aws_vpc.main.id", description="VPC ID")
        out = o.render()
        self.assertIn('output "vpc_id"', out)
        self.assertIn("aws_vpc.main.id", out)

    def test_sensitive_output(self) -> None:
        o = TerraformOutput(name="secret", value="var.s", sensitive=True)
        self.assertIn("sensitive   = true", o.render())


class TestTerraformResource(unittest.TestCase):
    def test_render(self) -> None:
        r = TerraformResource(
            resource_type="aws_instance",
            name="web",
            attributes={"ami": "ami-123", "instance_type": "t2.micro"},
        )
        out = r.render()
        self.assertIn('resource "aws_instance" "web"', out)
        self.assertIn('"ami-123"', out)

    def test_empty_attrs(self) -> None:
        r = TerraformResource(resource_type="null_resource", name="empty")
        out = r.render()
        self.assertIn('resource "null_resource" "empty"', out)


class TestTerraformProvider(unittest.TestCase):
    def test_render_with_region(self) -> None:
        p = TerraformProvider(name="aws", region="us-east-1")
        out = p.render()
        self.assertIn('provider "aws"', out)
        self.assertIn('region = "us-east-1"', out)

    def test_render_no_region(self) -> None:
        p = TerraformProvider(name="null")
        out = p.render()
        self.assertIn('provider "null"', out)
        self.assertNotIn("region", out)


class TestTerraformModule(unittest.TestCase):
    def test_render(self) -> None:
        m = TerraformModule(
            name="vpc",
            source="terraform-aws-modules/vpc/aws",
            variables={"cidr": "10.0.0.0/16"},
        )
        out = m.render()
        self.assertIn('module "vpc"', out)
        self.assertIn("terraform-aws-modules/vpc/aws", out)
        self.assertIn('"10.0.0.0/16"', out)


class TestStateConfig(unittest.TestCase):
    def test_render_s3(self) -> None:
        s = StateConfig(
            backend="s3",
            config={"bucket": "my-state", "key": "terraform.tfstate"},
        )
        out = s.render()
        self.assertIn('backend "s3"', out)
        self.assertIn("my-state", out)


class TestTerraformConfig(unittest.TestCase):
    def test_render_empty(self) -> None:
        cfg = TerraformConfig()
        files = cfg.render()
        self.assertEqual(files, {})

    def test_render_full(self) -> None:
        cfg = TerraformConfig(
            providers=[TerraformProvider(name="aws", region="us-west-2")],
            resources=[TerraformResource("aws_s3_bucket", "data")],
            variables=[TerraformVariable(name="env")],
            outputs=[TerraformOutput(name="bucket_arn", value="aws_s3_bucket.data.arn")],
        )
        files = cfg.render()
        self.assertIn("main.tf", files)
        self.assertIn("variables.tf", files)
        self.assertIn("outputs.tf", files)


class TestTerraformGenerator(unittest.TestCase):
    def test_empty_generate(self) -> None:
        gen = TerraformGenerator()
        files = gen.generate()
        self.assertEqual(files, {})

    def test_add_provider_immutable(self) -> None:
        gen1 = TerraformGenerator()
        gen2 = gen1.add_provider("aws", region="us-east-1")
        self.assertIsNot(gen1, gen2)
        self.assertEqual(len(gen1.config.providers), 0)
        self.assertEqual(len(gen2.config.providers), 1)

    def test_add_resource(self) -> None:
        gen = TerraformGenerator().add_resource("aws_instance", "web", ami="ami-123")
        files = gen.generate()
        self.assertIn("main.tf", files)
        self.assertIn("aws_instance", files["main.tf"])

    def test_add_variable(self) -> None:
        gen = TerraformGenerator().add_variable("region", default="us-east-1")
        files = gen.generate()
        self.assertIn("variables.tf", files)

    def test_add_output(self) -> None:
        gen = TerraformGenerator().add_output("id", "aws_instance.web.id")
        files = gen.generate()
        self.assertIn("outputs.tf", files)

    def test_add_module(self) -> None:
        gen = TerraformGenerator().add_module("vpc", "source/vpc")
        files = gen.generate()
        self.assertIn('module "vpc"', files["main.tf"])

    def test_set_state(self) -> None:
        gen = TerraformGenerator().set_state("s3", bucket="my-state")
        files = gen.generate()
        self.assertIn("backend", files["main.tf"])

    def test_chained_build(self) -> None:
        gen = (
            TerraformGenerator()
            .add_provider("aws", region="eu-west-1")
            .add_resource("aws_s3_bucket", "logs")
            .add_variable("env", default="prod")
            .add_output("bucket", "aws_s3_bucket.logs.id")
            .set_state("s3", bucket="state-bucket")
        )
        files = gen.generate()
        self.assertIn("main.tf", files)
        self.assertIn("variables.tf", files)
        self.assertIn("outputs.tf", files)
        self.assertIn("aws", files["main.tf"])


if __name__ == "__main__":
    unittest.main()
