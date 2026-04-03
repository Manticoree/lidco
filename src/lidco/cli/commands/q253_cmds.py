"""Q253 CLI commands: /gen-tests, /edge-cases, /gen-mocks, /test-data."""
from __future__ import annotations


def register(registry) -> None:
    """Register Q253 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    # ------------------------------------------------------------------
    # /gen-tests
    # ------------------------------------------------------------------

    async def gen_tests_handler(args: str) -> str:
        from lidco.testgen.scaffolder import TestScaffolder

        scaffolder = TestScaffolder()
        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "scaffold":
            if not rest:
                return "Usage: /gen-tests scaffold <python source>"
            result = scaffolder.scaffold(rest)
            return result.test_file

        if sub == "file":
            if not rest:
                return "Usage: /gen-tests file <filename> <source>"
            file_parts = rest.split(maxsplit=1)
            filename = file_parts[0]
            source = file_parts[1] if len(file_parts) > 1 else ""
            return scaffolder.scaffold_for_file(filename, source)

        if sub == "functions":
            if not rest:
                return "Usage: /gen-tests functions <python source>"
            fns = scaffolder.extract_functions(rest)
            if not fns:
                return "No public functions found."
            return "Functions: " + ", ".join(fns)

        if sub == "classes":
            if not rest:
                return "Usage: /gen-tests classes <python source>"
            classes = scaffolder.extract_classes(rest)
            if not classes:
                return "No classes found."
            lines = []
            for cls in classes:
                methods = ", ".join(cls["methods"]) if cls["methods"] else "(none)"
                lines.append(f"{cls['name']}: {methods}")
            return "\n".join(lines)

        return (
            "Usage: /gen-tests <subcommand>\n"
            "  scaffold <source>         — generate test skeleton\n"
            "  file <filename> <source>  — generate full test file\n"
            "  functions <source>        — list public functions\n"
            "  classes <source>          — list classes and methods"
        )

    # ------------------------------------------------------------------
    # /edge-cases
    # ------------------------------------------------------------------

    async def edge_cases_handler(args: str) -> str:
        from lidco.testgen.edge_cases import EdgeCaseGenerator

        gen = EdgeCaseGenerator()
        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "type":
            if not rest:
                return "Usage: /edge-cases type <type_name>"
            cases = gen.for_type(rest)
            if not cases:
                return f"No edge cases for type '{rest}'."
            lines = [f"Edge cases for '{rest}':"]
            for ec in cases:
                lines.append(f"  [{ec.category}] {ec.description}: {ec.input_value!r}")
            return "\n".join(lines)

        if sub == "boundary":
            if not rest:
                return "Usage: /edge-cases boundary <min> <max>"
            nums = rest.split()
            if len(nums) < 2:
                return "Usage: /edge-cases boundary <min> <max>"
            values = gen.boundary_values(int(nums[0]), int(nums[1]))
            return "Boundary values: " + ", ".join(str(v) for v in values)

        if sub == "categories":
            cats = gen.categories()
            return "Categories: " + ", ".join(cats)

        return (
            "Usage: /edge-cases <subcommand>\n"
            "  type <type_name>     — edge cases for a type\n"
            "  boundary <min> <max> — boundary values for range\n"
            "  categories           — list all categories"
        )

    # ------------------------------------------------------------------
    # /gen-mocks
    # ------------------------------------------------------------------

    async def gen_mocks_handler(args: str) -> str:
        from lidco.testgen.mock_gen import MockGeneratorV2, MockSpec

        gen = MockGeneratorV2()
        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "generate":
            if not rest:
                return "Usage: /gen-mocks generate <name>"
            spec = MockSpec(name=rest)
            return gen.generate(spec)

        if sub == "from":
            if not rest:
                return "Usage: /gen-mocks from <class_name> <source>"
            from_parts = rest.split(maxsplit=1)
            cls_name = from_parts[0]
            source = from_parts[1] if len(from_parts) > 1 else ""
            spec = gen.from_interface(source, cls_name)
            return gen.generate(spec)

        if sub == "spy":
            if not rest:
                return "Usage: /gen-mocks spy <name>"
            spec = MockSpec(name=rest)
            return gen.generate_spy(spec)

        return (
            "Usage: /gen-mocks <subcommand>\n"
            "  generate <name>              — generate empty mock\n"
            "  from <class_name> <source>   — mock from source\n"
            "  spy <name>                   — generate spy class"
        )

    # ------------------------------------------------------------------
    # /test-data
    # ------------------------------------------------------------------

    async def test_data_handler(args: str) -> str:
        from lidco.testgen.data_factory import TestDataFactory

        factory = TestDataFactory()
        parts = args.strip().split(maxsplit=1)
        sub = parts[0].lower() if parts else ""
        rest = parts[1].strip() if len(parts) > 1 else ""

        if sub == "string":
            length = int(rest) if rest else 10
            return factory.random_string(length=length)

        if sub == "int":
            nums = rest.split() if rest else []
            lo = int(nums[0]) if len(nums) > 0 else 0
            hi = int(nums[1]) if len(nums) > 1 else 1000
            return str(factory.random_int(min_val=lo, max_val=hi))

        if sub == "email":
            return factory.random_email()

        return (
            "Usage: /test-data <subcommand>\n"
            "  string [length]      — random string\n"
            "  int [min] [max]      — random integer\n"
            "  email                — random email address"
        )

    registry.register(SlashCommand("gen-tests", "Generate test scaffolds from source", gen_tests_handler))
    registry.register(SlashCommand("edge-cases", "Generate edge-case inputs", edge_cases_handler))
    registry.register(SlashCommand("gen-mocks", "Generate mock classes", gen_mocks_handler))
    registry.register(SlashCommand("test-data", "Generate random test data", test_data_handler))
