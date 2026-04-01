"""Tests for lidco.ecosystem.cloud_connector."""

from lidco.ecosystem.cloud_connector import (
    CloudConnector,
    CloudProvider,
    CloudResource,
    LogEntry,
)


class TestEnumsAndDataclasses:
    def test_cloud_provider_values(self):
        assert CloudProvider.AWS.value == "aws"
        assert CloudProvider.GCP.value == "gcp"
        assert CloudProvider.AZURE.value == "azure"

    def test_cloud_resource_frozen(self):
        r = CloudResource(id="r1", name="my-fn", provider=CloudProvider.AWS, resource_type="lambda")
        assert r.id == "r1"
        assert r.region == ""
        assert r.status == "active"
        assert r.metadata == ()

    def test_log_entry_frozen(self):
        le = LogEntry(timestamp=1000.0, message="hello", level="WARN", source="app")
        assert le.message == "hello"
        assert le.level == "WARN"


class TestCloudConnector:
    def test_add_credential(self):
        cc = CloudConnector()
        cc.add_credential(CloudProvider.AWS, "access_key", "AKID123")
        assert cc.has_credential(CloudProvider.AWS)

    def test_has_credential_false(self):
        cc = CloudConnector()
        assert cc.has_credential(CloudProvider.AWS) is False

    def test_add_credential_multiple_keys(self):
        cc = CloudConnector()
        cc.add_credential(CloudProvider.AWS, "access_key", "AKID")
        cc.add_credential(CloudProvider.AWS, "secret_key", "SECRET")
        assert cc._credentials["aws"]["access_key"] == "AKID"
        assert cc._credentials["aws"]["secret_key"] == "SECRET"

    def test_add_credential_immutable(self):
        cc = CloudConnector()
        old = cc._credentials
        cc.add_credential(CloudProvider.GCP, "token", "tok")
        assert cc._credentials is not old

    def test_register_resource(self):
        cc = CloudConnector()
        res = cc.register_resource("my-fn", CloudProvider.AWS, "lambda", region="us-east-1")
        assert res.name == "my-fn"
        assert res.provider == CloudProvider.AWS
        assert res.resource_type == "lambda"
        assert res.region == "us-east-1"
        assert res.id.startswith("res_")

    def test_list_resources_all(self):
        cc = CloudConnector()
        cc.register_resource("fn1", CloudProvider.AWS, "lambda")
        cc.register_resource("vm1", CloudProvider.GCP, "compute")
        assert len(cc.list_resources()) == 2

    def test_list_resources_by_provider(self):
        cc = CloudConnector()
        cc.register_resource("fn1", CloudProvider.AWS, "lambda")
        cc.register_resource("vm1", CloudProvider.GCP, "compute")
        aws = cc.list_resources(provider=CloudProvider.AWS)
        assert len(aws) == 1
        assert aws[0].provider == CloudProvider.AWS

    def test_list_resources_by_type(self):
        cc = CloudConnector()
        cc.register_resource("fn1", CloudProvider.AWS, "lambda")
        cc.register_resource("fn2", CloudProvider.GCP, "lambda")
        cc.register_resource("vm1", CloudProvider.AWS, "compute")
        lambdas = cc.list_resources(resource_type="lambda")
        assert len(lambdas) == 2

    def test_list_resources_combined_filter(self):
        cc = CloudConnector()
        cc.register_resource("fn1", CloudProvider.AWS, "lambda")
        cc.register_resource("fn2", CloudProvider.GCP, "lambda")
        result = cc.list_resources(provider=CloudProvider.AWS, resource_type="lambda")
        assert len(result) == 1

    def test_get_resource_found(self):
        cc = CloudConnector()
        res = cc.register_resource("fn1", CloudProvider.AWS, "lambda")
        found = cc.get_resource(res.id)
        assert found is not None
        assert found.name == "fn1"

    def test_get_resource_not_found(self):
        cc = CloudConnector()
        assert cc.get_resource("nope") is None

    def test_add_log(self):
        cc = CloudConnector()
        entry = cc.add_log("hello world", level="WARN", source="app")
        assert entry.message == "hello world"
        assert entry.level == "WARN"
        assert entry.source == "app"

    def test_tail_logs_all(self):
        cc = CloudConnector()
        cc.add_log("msg1")
        cc.add_log("msg2")
        logs = cc.tail_logs()
        assert len(logs) == 2

    def test_tail_logs_by_source(self):
        cc = CloudConnector()
        cc.add_log("a", source="app")
        cc.add_log("b", source="db")
        logs = cc.tail_logs(source="app")
        assert len(logs) == 1
        assert logs[0].source == "app"

    def test_tail_logs_limit(self):
        cc = CloudConnector()
        for i in range(10):
            cc.add_log(f"msg{i}")
        logs = cc.tail_logs(limit=3)
        assert len(logs) == 3

    def test_invoke_function(self):
        cc = CloudConnector()
        result = cc.invoke_function("res_1", payload={"key": "value"})
        assert result["resource"] == "res_1"
        assert result["status"] == "invoked"
        assert result["payload"] == {"key": "value"}

    def test_invoke_function_no_payload(self):
        cc = CloudConnector()
        result = cc.invoke_function("res_1")
        assert result["payload"] is None

    def test_summary_empty(self):
        cc = CloudConnector()
        assert cc.summary() == "No cloud resources."

    def test_summary_with_resources(self):
        cc = CloudConnector()
        cc.register_resource("fn1", CloudProvider.AWS, "lambda")
        s = cc.summary()
        assert "Cloud resources: 1" in s
        assert "fn1" in s
        assert "aws" in s
