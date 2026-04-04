"""K8sManifestGenerator — generate Kubernetes manifests (stdlib only)."""
from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from typing import Any


class K8sManifestGenerator:
    """Generate Kubernetes resource manifests as plain dicts."""

    def __init__(self, namespace: str = "default") -> None:
        self._namespace = namespace

    # ------------------------------------------------------------------ #
    # Deployment                                                           #
    # ------------------------------------------------------------------ #

    def deployment(
        self,
        name: str,
        image: str,
        replicas: int = 1,
        *,
        port: int | None = None,
        env: dict[str, str] | None = None,
        labels: dict[str, str] | None = None,
        resources: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Return a Deployment manifest dict."""
        lbl = {"app": name}
        if labels:
            lbl.update(labels)

        container: dict[str, Any] = {
            "name": name,
            "image": image,
        }
        if port is not None:
            container["ports"] = [{"containerPort": port}]
        if env:
            container["env"] = [{"name": k, "value": v} for k, v in sorted(env.items())]
        if resources:
            container["resources"] = resources

        return {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": name,
                "namespace": self._namespace,
                "labels": dict(lbl),
            },
            "spec": {
                "replicas": replicas,
                "selector": {"matchLabels": {"app": name}},
                "template": {
                    "metadata": {"labels": dict(lbl)},
                    "spec": {
                        "containers": [container],
                    },
                },
            },
        }

    # ------------------------------------------------------------------ #
    # Service                                                              #
    # ------------------------------------------------------------------ #

    def service(
        self,
        name: str,
        port: int,
        *,
        target_port: int | None = None,
        service_type: str = "ClusterIP",
        labels: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Return a Service manifest dict."""
        lbl = {"app": name}
        if labels:
            lbl.update(labels)

        return {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {
                "name": name,
                "namespace": self._namespace,
                "labels": dict(lbl),
            },
            "spec": {
                "type": service_type,
                "selector": {"app": name},
                "ports": [
                    {
                        "port": port,
                        "targetPort": target_port or port,
                        "protocol": "TCP",
                    }
                ],
            },
        }

    # ------------------------------------------------------------------ #
    # Ingress                                                              #
    # ------------------------------------------------------------------ #

    def ingress(
        self,
        name: str,
        host: str,
        path: str = "/",
        *,
        service_name: str | None = None,
        service_port: int = 80,
        tls: bool = False,
        annotations: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Return an Ingress manifest dict."""
        svc_name = service_name or name
        rule: dict[str, Any] = {
            "host": host,
            "http": {
                "paths": [
                    {
                        "path": path,
                        "pathType": "Prefix",
                        "backend": {
                            "service": {
                                "name": svc_name,
                                "port": {"number": service_port},
                            }
                        },
                    }
                ]
            },
        }
        manifest: dict[str, Any] = {
            "apiVersion": "networking.k8s.io/v1",
            "kind": "Ingress",
            "metadata": {
                "name": name,
                "namespace": self._namespace,
                "annotations": dict(annotations or {}),
            },
            "spec": {
                "rules": [rule],
            },
        }
        if tls:
            manifest["spec"]["tls"] = [
                {"hosts": [host], "secretName": f"{name}-tls"}
            ]
        return manifest

    # ------------------------------------------------------------------ #
    # Helm chart skeleton                                                  #
    # ------------------------------------------------------------------ #

    def helm_chart(
        self,
        name: str,
        *,
        version: str = "0.1.0",
        app_version: str = "1.0.0",
        description: str = "",
    ) -> dict[str, Any]:
        """Return a dict representing a Helm chart skeleton.

        Keys:
          - ``Chart.yaml`` — chart metadata
          - ``values.yaml`` — default values
          - ``templates/deployment.yaml`` — deployment template
          - ``templates/service.yaml`` — service template
        """
        chart_yaml = {
            "apiVersion": "v2",
            "name": name,
            "version": version,
            "appVersion": app_version,
            "description": description or f"Helm chart for {name}",
            "type": "application",
        }
        values_yaml = {
            "replicaCount": 1,
            "image": {
                "repository": name,
                "tag": app_version,
                "pullPolicy": "IfNotPresent",
            },
            "service": {
                "type": "ClusterIP",
                "port": 80,
            },
            "resources": {},
        }
        deployment_tpl = (
            "apiVersion: apps/v1\n"
            "kind: Deployment\n"
            "metadata:\n"
            "  name: {{ .Release.Name }}\n"
            "spec:\n"
            "  replicas: {{ .Values.replicaCount }}\n"
            "  selector:\n"
            "    matchLabels:\n"
            "      app: {{ .Release.Name }}\n"
            "  template:\n"
            "    metadata:\n"
            "      labels:\n"
            "        app: {{ .Release.Name }}\n"
            "    spec:\n"
            "      containers:\n"
            "        - name: {{ .Release.Name }}\n"
            "          image: {{ .Values.image.repository }}:{{ .Values.image.tag }}\n"
        )
        service_tpl = (
            "apiVersion: v1\n"
            "kind: Service\n"
            "metadata:\n"
            "  name: {{ .Release.Name }}\n"
            "spec:\n"
            "  type: {{ .Values.service.type }}\n"
            "  ports:\n"
            "    - port: {{ .Values.service.port }}\n"
            "  selector:\n"
            "    app: {{ .Release.Name }}\n"
        )
        return {
            "Chart.yaml": chart_yaml,
            "values.yaml": values_yaml,
            "templates/deployment.yaml": deployment_tpl,
            "templates/service.yaml": service_tpl,
        }
