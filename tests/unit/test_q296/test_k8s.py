"""Tests for Q296 K8sManifestGenerator."""
import unittest

from lidco.containers.k8s import K8sManifestGenerator


class TestK8sManifestGenerator(unittest.TestCase):
    def setUp(self):
        self.gen = K8sManifestGenerator(namespace="test-ns")

    # -- deployment --------------------------------------------------------

    def test_deployment_basic(self):
        d = self.gen.deployment("myapp", "myapp:1.0")
        self.assertEqual(d["kind"], "Deployment")
        self.assertEqual(d["apiVersion"], "apps/v1")
        self.assertEqual(d["metadata"]["name"], "myapp")
        self.assertEqual(d["metadata"]["namespace"], "test-ns")
        self.assertEqual(d["spec"]["replicas"], 1)

    def test_deployment_replicas(self):
        d = self.gen.deployment("myapp", "myapp:1.0", replicas=3)
        self.assertEqual(d["spec"]["replicas"], 3)

    def test_deployment_with_port(self):
        d = self.gen.deployment("myapp", "myapp:1.0", port=8080)
        container = d["spec"]["template"]["spec"]["containers"][0]
        self.assertEqual(container["ports"], [{"containerPort": 8080}])

    def test_deployment_with_env(self):
        d = self.gen.deployment("myapp", "myapp:1.0", env={"DB_HOST": "localhost"})
        container = d["spec"]["template"]["spec"]["containers"][0]
        self.assertEqual(container["env"], [{"name": "DB_HOST", "value": "localhost"}])

    def test_deployment_with_labels(self):
        d = self.gen.deployment("myapp", "myapp:1.0", labels={"tier": "frontend"})
        self.assertIn("tier", d["metadata"]["labels"])
        self.assertEqual(d["metadata"]["labels"]["tier"], "frontend")
        self.assertEqual(d["metadata"]["labels"]["app"], "myapp")

    def test_deployment_with_resources(self):
        res = {"limits": {"cpu": "500m", "memory": "256Mi"}}
        d = self.gen.deployment("myapp", "myapp:1.0", resources=res)
        container = d["spec"]["template"]["spec"]["containers"][0]
        self.assertEqual(container["resources"], res)

    def test_deployment_selector_matches_labels(self):
        d = self.gen.deployment("myapp", "myapp:1.0")
        sel = d["spec"]["selector"]["matchLabels"]
        tpl_labels = d["spec"]["template"]["metadata"]["labels"]
        self.assertEqual(sel["app"], "myapp")
        self.assertEqual(tpl_labels["app"], "myapp")

    def test_deployment_container_image(self):
        d = self.gen.deployment("myapp", "myapp:2.0")
        container = d["spec"]["template"]["spec"]["containers"][0]
        self.assertEqual(container["name"], "myapp")
        self.assertEqual(container["image"], "myapp:2.0")

    # -- service -----------------------------------------------------------

    def test_service_basic(self):
        s = self.gen.service("myapp", 80)
        self.assertEqual(s["kind"], "Service")
        self.assertEqual(s["apiVersion"], "v1")
        self.assertEqual(s["metadata"]["name"], "myapp")
        self.assertEqual(s["spec"]["type"], "ClusterIP")
        self.assertEqual(s["spec"]["ports"][0]["port"], 80)
        self.assertEqual(s["spec"]["ports"][0]["targetPort"], 80)

    def test_service_custom_target_port(self):
        s = self.gen.service("myapp", 80, target_port=8080)
        self.assertEqual(s["spec"]["ports"][0]["targetPort"], 8080)

    def test_service_loadbalancer(self):
        s = self.gen.service("myapp", 80, service_type="LoadBalancer")
        self.assertEqual(s["spec"]["type"], "LoadBalancer")

    def test_service_selector(self):
        s = self.gen.service("myapp", 80)
        self.assertEqual(s["spec"]["selector"], {"app": "myapp"})

    # -- ingress -----------------------------------------------------------

    def test_ingress_basic(self):
        ing = self.gen.ingress("myapp", "example.com")
        self.assertEqual(ing["kind"], "Ingress")
        self.assertEqual(ing["apiVersion"], "networking.k8s.io/v1")
        rule = ing["spec"]["rules"][0]
        self.assertEqual(rule["host"], "example.com")
        path_entry = rule["http"]["paths"][0]
        self.assertEqual(path_entry["path"], "/")
        self.assertEqual(path_entry["pathType"], "Prefix")

    def test_ingress_custom_path(self):
        ing = self.gen.ingress("myapp", "example.com", "/api")
        path_entry = ing["spec"]["rules"][0]["http"]["paths"][0]
        self.assertEqual(path_entry["path"], "/api")

    def test_ingress_with_tls(self):
        ing = self.gen.ingress("myapp", "example.com", tls=True)
        self.assertIn("tls", ing["spec"])
        self.assertEqual(ing["spec"]["tls"][0]["hosts"], ["example.com"])
        self.assertEqual(ing["spec"]["tls"][0]["secretName"], "myapp-tls")

    def test_ingress_without_tls(self):
        ing = self.gen.ingress("myapp", "example.com")
        self.assertNotIn("tls", ing["spec"])

    def test_ingress_custom_service(self):
        ing = self.gen.ingress("myapp", "example.com", service_name="backend", service_port=8080)
        backend = ing["spec"]["rules"][0]["http"]["paths"][0]["backend"]
        self.assertEqual(backend["service"]["name"], "backend")
        self.assertEqual(backend["service"]["port"]["number"], 8080)

    def test_ingress_annotations(self):
        ing = self.gen.ingress("myapp", "example.com", annotations={"nginx.ingress.kubernetes.io/rewrite-target": "/"})
        self.assertEqual(ing["metadata"]["annotations"]["nginx.ingress.kubernetes.io/rewrite-target"], "/")

    # -- helm_chart --------------------------------------------------------

    def test_helm_chart_keys(self):
        chart = self.gen.helm_chart("myapp")
        self.assertIn("Chart.yaml", chart)
        self.assertIn("values.yaml", chart)
        self.assertIn("templates/deployment.yaml", chart)
        self.assertIn("templates/service.yaml", chart)

    def test_helm_chart_metadata(self):
        chart = self.gen.helm_chart("myapp", version="1.2.3", app_version="2.0.0")
        meta = chart["Chart.yaml"]
        self.assertEqual(meta["name"], "myapp")
        self.assertEqual(meta["version"], "1.2.3")
        self.assertEqual(meta["appVersion"], "2.0.0")
        self.assertEqual(meta["apiVersion"], "v2")

    def test_helm_chart_values(self):
        chart = self.gen.helm_chart("myapp")
        vals = chart["values.yaml"]
        self.assertEqual(vals["replicaCount"], 1)
        self.assertEqual(vals["image"]["repository"], "myapp")
        self.assertEqual(vals["service"]["type"], "ClusterIP")

    def test_helm_chart_templates_are_strings(self):
        chart = self.gen.helm_chart("myapp")
        self.assertIsInstance(chart["templates/deployment.yaml"], str)
        self.assertIsInstance(chart["templates/service.yaml"], str)
        self.assertIn("{{ .Release.Name }}", chart["templates/deployment.yaml"])

    def test_default_namespace(self):
        gen = K8sManifestGenerator()
        d = gen.deployment("app", "img:1")
        self.assertEqual(d["metadata"]["namespace"], "default")


if __name__ == "__main__":
    unittest.main()
