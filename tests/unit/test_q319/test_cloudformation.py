"""Tests for lidco.iac.cloudformation — CloudFormationGenerator, drift detection."""

from __future__ import annotations

import json
import unittest

from lidco.iac.cloudformation import (
    CFOutput,
    CFParameter,
    CFResource,
    CFTemplate,
    CloudFormationGenerator,
    DriftResult,
    NestedStack,
)


class TestCFParameter(unittest.TestCase):
    def test_render_minimal(self) -> None:
        p = CFParameter(name="Env")
        d = p.render()
        self.assertEqual(d["Type"], "String")

    def test_render_full(self) -> None:
        p = CFParameter(
            name="Env",
            type="String",
            description="Environment",
            default="prod",
            allowed_values=["dev", "prod"],
        )
        d = p.render()
        self.assertEqual(d["Default"], "prod")
        self.assertEqual(d["AllowedValues"], ["dev", "prod"])
        self.assertEqual(d["Description"], "Environment")

    def test_frozen(self) -> None:
        p = CFParameter(name="X")
        with self.assertRaises(AttributeError):
            p.name = "Y"  # type: ignore[misc]


class TestCFResource(unittest.TestCase):
    def test_render(self) -> None:
        r = CFResource(
            logical_id="MyBucket",
            resource_type="AWS::S3::Bucket",
            properties={"BucketName": "my-bucket"},
        )
        d = r.render()
        self.assertEqual(d["Type"], "AWS::S3::Bucket")
        self.assertEqual(d["Properties"]["BucketName"], "my-bucket")

    def test_depends_on(self) -> None:
        r = CFResource(
            logical_id="App",
            resource_type="AWS::EC2::Instance",
            depends_on=["VPC"],
        )
        d = r.render()
        self.assertEqual(d["DependsOn"], ["VPC"])

    def test_no_properties(self) -> None:
        r = CFResource(logical_id="X", resource_type="AWS::SNS::Topic")
        d = r.render()
        self.assertNotIn("Properties", d)


class TestCFOutput(unittest.TestCase):
    def test_render(self) -> None:
        o = CFOutput(name="BucketArn", value={"Fn::GetAtt": ["Bucket", "Arn"]})
        d = o.render()
        self.assertIn("Value", d)

    def test_export(self) -> None:
        o = CFOutput(name="VpcId", value="vpc-123", export_name="MyVpcId")
        d = o.render()
        self.assertEqual(d["Export"]["Name"], "MyVpcId")


class TestNestedStack(unittest.TestCase):
    def test_as_resource(self) -> None:
        ns = NestedStack(
            logical_id="NetworkStack",
            template_url="https://s3.amazonaws.com/net.yaml",
            parameters={"CIDR": "10.0.0.0/16"},
        )
        r = ns.as_resource()
        self.assertEqual(r.resource_type, "AWS::CloudFormation::Stack")
        self.assertEqual(r.logical_id, "NetworkStack")
        d = r.render()
        self.assertEqual(d["Properties"]["TemplateURL"], "https://s3.amazonaws.com/net.yaml")


class TestCFTemplate(unittest.TestCase):
    def test_render_empty(self) -> None:
        t = CFTemplate()
        d = t.render()
        self.assertEqual(d["AWSTemplateFormatVersion"], "2010-09-09")
        self.assertNotIn("Resources", d)

    def test_render_with_resources(self) -> None:
        t = CFTemplate(
            description="Test",
            resources=[CFResource("Bucket", "AWS::S3::Bucket")],
        )
        d = t.render()
        self.assertIn("Bucket", d["Resources"])
        self.assertEqual(d["Description"], "Test")

    def test_to_json(self) -> None:
        t = CFTemplate(resources=[CFResource("X", "AWS::SNS::Topic")])
        j = t.to_json()
        parsed = json.loads(j)
        self.assertIn("X", parsed["Resources"])

    def test_nested_stacks_in_render(self) -> None:
        t = CFTemplate(
            nested_stacks=[NestedStack("Sub", "https://example.com/sub.yaml")],
        )
        d = t.render()
        self.assertIn("Sub", d["Resources"])

    def test_parameters_and_outputs(self) -> None:
        t = CFTemplate(
            parameters=[CFParameter("Env")],
            outputs=[CFOutput("Id", "x")],
            resources=[CFResource("R", "AWS::SNS::Topic")],
        )
        d = t.render()
        self.assertIn("Env", d["Parameters"])
        self.assertIn("Id", d["Outputs"])


class TestCloudFormationGenerator(unittest.TestCase):
    def test_empty_generate(self) -> None:
        gen = CloudFormationGenerator()
        files = gen.generate()
        self.assertIn("template.json", files)

    def test_add_parameter_immutable(self) -> None:
        gen1 = CloudFormationGenerator()
        gen2 = gen1.add_parameter("Env")
        self.assertIsNot(gen1, gen2)
        self.assertEqual(len(gen1.template.parameters), 0)
        self.assertEqual(len(gen2.template.parameters), 1)

    def test_add_resource(self) -> None:
        gen = CloudFormationGenerator().add_resource("Bucket", "AWS::S3::Bucket")
        files = gen.generate()
        parsed = json.loads(files["template.json"])
        self.assertIn("Bucket", parsed["Resources"])

    def test_add_output(self) -> None:
        gen = CloudFormationGenerator().add_output("Id", "val", export_name="ExId")
        files = gen.generate()
        parsed = json.loads(files["template.json"])
        self.assertIn("Id", parsed["Outputs"])

    def test_add_nested_stack(self) -> None:
        gen = CloudFormationGenerator().add_nested_stack("Sub", "https://example.com/s.yaml")
        parsed = json.loads(gen.generate()["template.json"])
        self.assertIn("Sub", parsed["Resources"])

    def test_chained_build(self) -> None:
        gen = (
            CloudFormationGenerator(description="My stack")
            .add_parameter("Env", default="dev")
            .add_resource("Bucket", "AWS::S3::Bucket", {"BucketName": "test"})
            .add_output("BucketArn", {"Fn::GetAtt": ["Bucket", "Arn"]})
        )
        parsed = json.loads(gen.generate()["template.json"])
        self.assertEqual(parsed["Description"], "My stack")
        self.assertIn("Env", parsed["Parameters"])
        self.assertIn("Bucket", parsed["Resources"])


class TestDriftDetection(unittest.TestCase):
    def test_no_drift(self) -> None:
        t = CFTemplate(resources=[CFResource("A", "AWS::S3::Bucket")])
        result = CloudFormationGenerator.detect_drift(t, t)
        self.assertFalse(result.has_drift)

    def test_added_resource(self) -> None:
        expected = CFTemplate(resources=[CFResource("A", "AWS::S3::Bucket")])
        actual = CFTemplate(
            resources=[
                CFResource("A", "AWS::S3::Bucket"),
                CFResource("B", "AWS::SNS::Topic"),
            ]
        )
        result = CloudFormationGenerator.detect_drift(expected, actual)
        self.assertTrue(result.has_drift)
        self.assertIn("B", result.added)

    def test_removed_resource(self) -> None:
        expected = CFTemplate(
            resources=[
                CFResource("A", "AWS::S3::Bucket"),
                CFResource("B", "AWS::SNS::Topic"),
            ]
        )
        actual = CFTemplate(resources=[CFResource("A", "AWS::S3::Bucket")])
        result = CloudFormationGenerator.detect_drift(expected, actual)
        self.assertTrue(result.has_drift)
        self.assertIn("B", result.removed)

    def test_modified_resource(self) -> None:
        expected = CFTemplate(
            resources=[CFResource("A", "AWS::S3::Bucket", {"BucketName": "old"})]
        )
        actual = CFTemplate(
            resources=[CFResource("A", "AWS::S3::Bucket", {"BucketName": "new"})]
        )
        result = CloudFormationGenerator.detect_drift(expected, actual)
        self.assertTrue(result.has_drift)
        self.assertIn("A", result.modified)


if __name__ == "__main__":
    unittest.main()
