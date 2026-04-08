"""Tests for lidco.envmgmt.provisioner — EnvProvisioner."""

from __future__ import annotations

import unittest

from lidco.envmgmt.provisioner import (
    EnvProvisioner,
    EnvStatus,
    EnvTemplate,
    EnvTier,
    Environment,
    ProvisionError,
)


class TestEnvTemplate(unittest.TestCase):
    def test_template_creation(self) -> None:
        t = EnvTemplate(name="web", tier=EnvTier.DEV)
        self.assertEqual(t.name, "web")
        self.assertEqual(t.tier, EnvTier.DEV)
        self.assertEqual(t.config, {})
        self.assertEqual(t.resources, {})
        self.assertEqual(t.tags, {})

    def test_template_with_config(self) -> None:
        t = EnvTemplate(
            name="api",
            tier=EnvTier.PROD,
            config={"replicas": 5},
            tags={"team": "backend"},
        )
        self.assertEqual(t.config["replicas"], 5)
        self.assertEqual(t.tags["team"], "backend")


class TestEnvProvisioner(unittest.TestCase):
    def setUp(self) -> None:
        self.provisioner = EnvProvisioner()
        self.template = EnvTemplate(
            name="web-app",
            tier=EnvTier.DEV,
            config={"port": 8080},
            resources={"cpu": "1 core"},
            tags={"owner": "alice"},
        )
        self.provisioner.register_template(self.template)

    def test_register_and_get_template(self) -> None:
        t = self.provisioner.get_template("web-app")
        self.assertIsNotNone(t)
        self.assertEqual(t.name, "web-app")

    def test_get_template_missing(self) -> None:
        self.assertIsNone(self.provisioner.get_template("nope"))

    def test_list_templates(self) -> None:
        templates = self.provisioner.list_templates()
        self.assertEqual(len(templates), 1)
        self.assertEqual(templates[0].name, "web-app")

    def test_provision_basic(self) -> None:
        env = self.provisioner.provision("web-app")
        self.assertIsInstance(env, Environment)
        self.assertEqual(env.tier, EnvTier.DEV)
        self.assertEqual(env.status, EnvStatus.ACTIVE)
        self.assertIn("port", env.config)
        self.assertEqual(env.config["port"], 8080)
        # Auto-configured tier defaults merged
        self.assertTrue(env.config.get("debug"))
        self.assertEqual(env.config.get("replicas"), 1)

    def test_provision_name_override(self) -> None:
        env = self.provisioner.provision("web-app", name_override="my-env")
        self.assertEqual(env.name, "my-env")

    def test_provision_extra_config(self) -> None:
        env = self.provisioner.provision(
            "web-app", extra_config={"feature_x": True}
        )
        self.assertTrue(env.config["feature_x"])

    def test_provision_extra_tags(self) -> None:
        env = self.provisioner.provision("web-app", extra_tags={"env": "ci"})
        self.assertEqual(env.tags["env"], "ci")
        self.assertEqual(env.tags["owner"], "alice")

    def test_provision_unknown_template(self) -> None:
        with self.assertRaises(ProvisionError):
            self.provisioner.provision("unknown")

    def test_provision_duplicate_name(self) -> None:
        self.provisioner.provision("web-app", name_override="dup")
        with self.assertRaises(ProvisionError):
            self.provisioner.provision("web-app", name_override="dup")

    def test_auto_configure_staging(self) -> None:
        tmpl = EnvTemplate(name="stg", tier=EnvTier.STAGING)
        self.provisioner.register_template(tmpl)
        env = self.provisioner.provision("stg")
        self.assertEqual(env.config["replicas"], 2)
        self.assertFalse(env.config["debug"])

    def test_auto_configure_prod(self) -> None:
        tmpl = EnvTemplate(name="prd", tier=EnvTier.PROD)
        self.provisioner.register_template(tmpl)
        env = self.provisioner.provision("prd")
        self.assertEqual(env.config["replicas"], 3)
        self.assertEqual(env.config["log_level"], "WARNING")

    def test_get_environment(self) -> None:
        env = self.provisioner.provision("web-app")
        found = self.provisioner.get(env.env_id)
        self.assertIs(found, env)

    def test_get_environment_missing(self) -> None:
        self.assertIsNone(self.provisioner.get("nonexistent"))

    def test_list_environments_all(self) -> None:
        self.provisioner.provision("web-app", name_override="e1")
        self.provisioner.provision("web-app", name_override="e2")
        envs = self.provisioner.list_environments()
        self.assertEqual(len(envs), 2)

    def test_list_environments_by_tier(self) -> None:
        tmpl2 = EnvTemplate(name="stg2", tier=EnvTier.STAGING)
        self.provisioner.register_template(tmpl2)
        self.provisioner.provision("web-app", name_override="d1")
        self.provisioner.provision("stg2", name_override="s1")
        devs = self.provisioner.list_environments(tier=EnvTier.DEV)
        self.assertEqual(len(devs), 1)

    def test_list_environments_by_status(self) -> None:
        env = self.provisioner.provision("web-app")
        self.provisioner.destroy(env.env_id)
        active = self.provisioner.list_environments(status=EnvStatus.ACTIVE)
        self.assertEqual(len(active), 0)
        destroyed = self.provisioner.list_environments(status=EnvStatus.DESTROYED)
        self.assertEqual(len(destroyed), 1)

    def test_destroy(self) -> None:
        env = self.provisioner.provision("web-app")
        result = self.provisioner.destroy(env.env_id)
        self.assertEqual(result.status, EnvStatus.DESTROYED)

    def test_destroy_missing(self) -> None:
        with self.assertRaises(ProvisionError):
            self.provisioner.destroy("no-such-id")

    def test_destroy_already_destroyed(self) -> None:
        env = self.provisioner.provision("web-app")
        self.provisioner.destroy(env.env_id)
        with self.assertRaises(ProvisionError):
            self.provisioner.destroy(env.env_id)

    def test_environment_to_dict(self) -> None:
        env = self.provisioner.provision("web-app", name_override="dictenv")
        d = env.to_dict()
        self.assertEqual(d["name"], "dictenv")
        self.assertEqual(d["tier"], "dev")
        self.assertEqual(d["status"], "active")
        self.assertIn("env_id", d)

    def test_provision_after_destroy_same_name(self) -> None:
        env = self.provisioner.provision("web-app", name_override="reuse")
        self.provisioner.destroy(env.env_id)
        env2 = self.provisioner.provision("web-app", name_override="reuse")
        self.assertEqual(env2.status, EnvStatus.ACTIVE)
        self.assertNotEqual(env.env_id, env2.env_id)


class TestEnvTierAndStatus(unittest.TestCase):
    def test_tier_values(self) -> None:
        self.assertEqual(EnvTier.DEV.value, "dev")
        self.assertEqual(EnvTier.STAGING.value, "staging")
        self.assertEqual(EnvTier.PROD.value, "prod")

    def test_status_values(self) -> None:
        self.assertEqual(EnvStatus.ACTIVE.value, "active")
        self.assertEqual(EnvStatus.DESTROYED.value, "destroyed")
        self.assertEqual(EnvStatus.FAILED.value, "failed")


if __name__ == "__main__":
    unittest.main()
