"""Tests for lidco.ecosystem.deploy_automator."""

from lidco.ecosystem.deploy_automator import (
    DeployAutomator,
    DeployStatus,
    DeployTarget,
    Deployment,
    Environment,
)


class TestEnumsAndDataclasses:
    def test_deploy_target_values(self):
        assert DeployTarget.VERCEL.value == "vercel"
        assert DeployTarget.NETLIFY.value == "netlify"
        assert DeployTarget.FLY_IO.value == "fly_io"
        assert DeployTarget.RAILWAY.value == "railway"
        assert DeployTarget.CUSTOM.value == "custom"

    def test_deploy_status_values(self):
        assert DeployStatus.PENDING.value == "pending"
        assert DeployStatus.LIVE.value == "live"
        assert DeployStatus.ROLLED_BACK.value == "rolled_back"

    def test_environment_frozen(self):
        env = Environment(name="prod", target=DeployTarget.VERCEL, url="https://prod.example.com")
        assert env.name == "prod"
        assert env.variables == ()

    def test_deployment_frozen(self):
        dep = Deployment(id="d1", environment="prod", target=DeployTarget.VERCEL)
        assert dep.status == DeployStatus.PENDING
        assert dep.commit == ""


class TestDeployAutomator:
    def test_add_environment(self):
        auto = DeployAutomator()
        env = auto.add_environment("staging", DeployTarget.NETLIFY, url="https://staging.example.com")
        assert env.name == "staging"
        assert env.target == DeployTarget.NETLIFY
        assert env.url == "https://staging.example.com"

    def test_add_environment_with_variables(self):
        auto = DeployAutomator()
        env = auto.add_environment("prod", DeployTarget.VERCEL, variables=(("API_KEY", "abc"),))
        assert env.variables == (("API_KEY", "abc"),)

    def test_add_environment_immutable(self):
        auto = DeployAutomator()
        old = auto._environments
        auto.add_environment("prod", DeployTarget.VERCEL)
        assert auto._environments is not old

    def test_deploy_success(self):
        auto = DeployAutomator()
        auto.add_environment("prod", DeployTarget.VERCEL)
        dep = auto.deploy("prod", commit="abc123")
        assert dep is not None
        assert dep.environment == "prod"
        assert dep.commit == "abc123"
        assert dep.status == DeployStatus.PENDING
        assert dep.target == DeployTarget.VERCEL

    def test_deploy_unknown_env(self):
        auto = DeployAutomator()
        assert auto.deploy("nonexistent") is None

    def test_deploy_default_commit(self):
        auto = DeployAutomator()
        auto.add_environment("staging", DeployTarget.NETLIFY)
        dep = auto.deploy("staging")
        assert dep is not None
        assert dep.commit == "HEAD"

    def test_rollback(self):
        auto = DeployAutomator()
        auto.add_environment("prod", DeployTarget.VERCEL)
        dep = auto.deploy("prod")
        assert dep is not None
        rolled = auto.rollback(dep.id)
        assert rolled is not None
        assert rolled.status == DeployStatus.ROLLED_BACK
        assert rolled.environment == "prod"
        assert rolled.id != dep.id

    def test_rollback_not_found(self):
        auto = DeployAutomator()
        assert auto.rollback("nonexistent") is None

    def test_get_deployment(self):
        auto = DeployAutomator()
        auto.add_environment("prod", DeployTarget.VERCEL)
        dep = auto.deploy("prod")
        assert dep is not None
        found = auto.get_deployment(dep.id)
        assert found is not None
        assert found.id == dep.id

    def test_get_deployment_not_found(self):
        auto = DeployAutomator()
        assert auto.get_deployment("none") is None

    def test_list_deployments_all(self):
        auto = DeployAutomator()
        auto.add_environment("prod", DeployTarget.VERCEL)
        auto.add_environment("staging", DeployTarget.NETLIFY)
        auto.deploy("prod")
        auto.deploy("staging")
        assert len(auto.list_deployments()) == 2

    def test_list_deployments_filtered(self):
        auto = DeployAutomator()
        auto.add_environment("prod", DeployTarget.VERCEL)
        auto.add_environment("staging", DeployTarget.NETLIFY)
        auto.deploy("prod")
        auto.deploy("staging")
        deps = auto.list_deployments(env_name="prod")
        assert len(deps) == 1
        assert deps[0].environment == "prod"

    def test_list_deployments_limit(self):
        auto = DeployAutomator()
        auto.add_environment("prod", DeployTarget.VERCEL)
        for _ in range(5):
            auto.deploy("prod")
        assert len(auto.list_deployments(limit=2)) == 2

    def test_health_check_known(self):
        auto = DeployAutomator()
        auto.add_environment("prod", DeployTarget.VERCEL, url="https://prod.example.com")
        hc = auto.health_check("prod")
        assert hc["status"] == "healthy"
        assert hc["url"] == "https://prod.example.com"

    def test_health_check_unknown(self):
        auto = DeployAutomator()
        hc = auto.health_check("nonexistent")
        assert hc["status"] == "unknown"

    def test_summary_empty(self):
        auto = DeployAutomator()
        assert auto.summary() == "No deployments."

    def test_summary_with_deployments(self):
        auto = DeployAutomator()
        auto.add_environment("prod", DeployTarget.VERCEL)
        auto.deploy("prod")
        s = auto.summary()
        assert "Deployments: 1" in s
        assert "prod" in s
