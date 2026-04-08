"""
Q319 CLI commands — /terraform, /cloudformation, /pulumi, /validate-iac

Registered via register_q319_commands(registry).
"""

from __future__ import annotations

import shlex


def register_q319_commands(registry) -> None:  # type: ignore[no-untyped-def]
    """Register Q319 slash commands onto the given registry."""

    # ------------------------------------------------------------------
    # /terraform — Generate Terraform configuration
    # ------------------------------------------------------------------
    async def terraform_handler(args: str) -> str:
        """
        Usage: /terraform --provider PROVIDER [--region REGION] [--resource TYPE:NAME ...] [--state BACKEND]
        """
        from lidco.iac.terraform import TerraformGenerator

        parts = shlex.split(args) if args.strip() else []
        provider = "aws"
        region = ""
        resources: list[tuple[str, str]] = []
        backend = ""

        i = 0
        while i < len(parts):
            if parts[i] == "--provider" and i + 1 < len(parts):
                provider = parts[i + 1]
                i += 2
            elif parts[i] == "--region" and i + 1 < len(parts):
                region = parts[i + 1]
                i += 2
            elif parts[i] == "--resource" and i + 1 < len(parts):
                spec = parts[i + 1]
                if ":" in spec:
                    rtype, rname = spec.split(":", 1)
                    resources.append((rtype, rname))
                i += 2
            elif parts[i] == "--state" and i + 1 < len(parts):
                backend = parts[i + 1]
                i += 2
            else:
                i += 1

        gen = TerraformGenerator()
        gen = gen.add_provider(provider, region=region)
        for rtype, rname in resources:
            gen = gen.add_resource(rtype, rname)
        if backend:
            gen = gen.set_state(backend)

        files = gen.generate()
        lines = [f"Generated {len(files)} Terraform file(s):"]
        for fname, content in files.items():
            lines.append(f"\n--- {fname} ---")
            lines.append(content)

        return "\n".join(lines)

    registry.register_async(
        "terraform",
        "Generate Terraform configuration",
        terraform_handler,
    )

    # ------------------------------------------------------------------
    # /cloudformation — Generate CloudFormation template
    # ------------------------------------------------------------------
    async def cloudformation_handler(args: str) -> str:
        """
        Usage: /cloudformation [--desc DESCRIPTION] [--resource LOGICAL_ID:TYPE ...] [--output NAME:VALUE ...]
        """
        from lidco.iac.cloudformation import CloudFormationGenerator

        parts = shlex.split(args) if args.strip() else []
        desc = ""
        resources: list[tuple[str, str]] = []
        outputs: list[tuple[str, str]] = []

        i = 0
        while i < len(parts):
            if parts[i] == "--desc" and i + 1 < len(parts):
                desc = parts[i + 1]
                i += 2
            elif parts[i] == "--resource" and i + 1 < len(parts):
                spec = parts[i + 1]
                if ":" in spec:
                    lid, rtype = spec.split(":", 1)
                    resources.append((lid, rtype))
                i += 2
            elif parts[i] == "--output" and i + 1 < len(parts):
                spec = parts[i + 1]
                if ":" in spec:
                    oname, oval = spec.split(":", 1)
                    outputs.append((oname, oval))
                i += 2
            else:
                i += 1

        gen = CloudFormationGenerator(description=desc)
        for lid, rtype in resources:
            gen = gen.add_resource(lid, rtype)
        for oname, oval in outputs:
            gen = gen.add_output(oname, oval)

        files = gen.generate()
        lines = [f"Generated CloudFormation template:"]
        for fname, content in files.items():
            lines.append(f"\n--- {fname} ---")
            lines.append(content)

        return "\n".join(lines)

    registry.register_async(
        "cloudformation",
        "Generate CloudFormation template",
        cloudformation_handler,
    )

    # ------------------------------------------------------------------
    # /pulumi — Generate Pulumi program
    # ------------------------------------------------------------------
    async def pulumi_handler(args: str) -> str:
        """
        Usage: /pulumi [--name PROJECT] [--lang python|typescript] [--resource NAME:TYPE ...] [--stack NAME]
        """
        from lidco.iac.pulumi import PulumiGenerator

        parts = shlex.split(args) if args.strip() else []
        project = "my-infra"
        lang = "python"
        resources: list[tuple[str, str]] = []
        stacks: list[str] = []

        i = 0
        while i < len(parts):
            if parts[i] == "--name" and i + 1 < len(parts):
                project = parts[i + 1]
                i += 2
            elif parts[i] == "--lang" and i + 1 < len(parts):
                lang = parts[i + 1]
                i += 2
            elif parts[i] == "--resource" and i + 1 < len(parts):
                spec = parts[i + 1]
                if ":" in spec:
                    rname, rtype = spec.split(":", 1)
                    resources.append((rname, rtype))
                i += 2
            elif parts[i] == "--stack" and i + 1 < len(parts):
                stacks.append(parts[i + 1])
                i += 2
            else:
                i += 1

        gen = PulumiGenerator(project_name=project, language=lang)
        for rname, rtype in resources:
            gen = gen.add_resource(rname, rtype)
        for s in stacks:
            gen = gen.add_stack(s)

        files = gen.generate()
        lines = [f"Generated {len(files)} Pulumi file(s):"]
        for fname, content in files.items():
            lines.append(f"\n--- {fname} ---")
            lines.append(content)

        return "\n".join(lines)

    registry.register_async(
        "pulumi",
        "Generate Pulumi program",
        pulumi_handler,
    )

    # ------------------------------------------------------------------
    # /validate-iac — Validate IaC templates
    # ------------------------------------------------------------------
    async def validate_iac_handler(args: str) -> str:
        """
        Usage: /validate-iac --type terraform|cloudformation|pulumi <file_content_or_path>
        """
        from lidco.iac.validator import IaCValidator

        parts = shlex.split(args) if args.strip() else []
        iac_type = "terraform"

        i = 0
        while i < len(parts):
            if parts[i] == "--type" and i + 1 < len(parts):
                iac_type = parts[i + 1]
                i += 2
            else:
                i += 1

        validator = IaCValidator()

        if iac_type == "cloudformation":
            import json as _json

            # Try to parse remaining args as JSON
            rest = " ".join(parts).replace(f"--type {iac_type}", "").strip()
            try:
                template = _json.loads(rest) if rest else {}
            except _json.JSONDecodeError:
                template = {}
            result = validator.validate_cloudformation(template)
        elif iac_type == "pulumi":
            result = validator.validate_pulumi({})
        else:
            result = validator.validate_terraform({})

        lines = [f"Validation ({iac_type}): {'PASS' if result.valid else 'FAIL'}"]
        if result.findings:
            lines.append(f"Findings ({len(result.findings)}):")
            for f in result.findings:
                lines.append(f"  [{f.severity.value}] {f.message}")
                if f.suggestion:
                    lines.append(f"    -> {f.suggestion}")
        if result.cost_estimates:
            lines.append(f"Estimated monthly cost: ${result.total_monthly_cost:.2f}")
            for c in result.cost_estimates:
                lines.append(f"  {c.resource} ({c.resource_type}): ${c.monthly_usd:.2f}/mo")

        return "\n".join(lines)

    registry.register_async(
        "validate-iac",
        "Validate IaC templates (security, cost, best practices)",
        validate_iac_handler,
    )
