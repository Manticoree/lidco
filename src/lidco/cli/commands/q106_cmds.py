"""Q106 CLI commands: /builder /strategy /template /decorator-pattern."""
from __future__ import annotations

_state: dict[str, object] = {}


def register(registry) -> None:
    """Register Q106 commands with *registry*."""
    from lidco.cli.commands.registry import SlashCommand

    async def builder_handler(args: str) -> str:
        """Usage: /builder <demo | build method url [timeout] | reset>"""
        from lidco.patterns.builder import HttpRequestBuilder, BuilderError
        if "builder" not in _state:
            _state["builder"] = HttpRequestBuilder()
        builder = _state["builder"]
        parts = args.strip().split(maxsplit=3)
        if not parts:
            return "Usage: /builder <demo | build method url | get url | post url | header key value | reset>"
        cmd = parts[0].lower()
        if cmd == "demo":
            req = (HttpRequestBuilder()
                   .get("https://api.example.com/users")
                   .header("Authorization", "Bearer token123")
                   .timeout(10.0)
                   .param("page", "1")
                   .build())
            return (
                f"method={req.method}\n"
                f"url={req.url}\n"
                f"headers={req.headers}\n"
                f"timeout={req.timeout}\n"
                f"params={req.params}"
            )
        elif cmd == "get":
            if len(parts) < 2:
                return "Usage: /builder get <url>"
            builder.get(parts[1])
            return f"Set: GET {parts[1]}"
        elif cmd == "post":
            if len(parts) < 2:
                return "Usage: /builder post <url>"
            builder.post(parts[1])
            return f"Set: POST {parts[1]}"
        elif cmd == "header":
            if len(parts) < 3:
                return "Usage: /builder header <key> <value>"
            builder.header(parts[1], parts[2])
            return f"Header set: {parts[1]}={parts[2]}"
        elif cmd == "timeout":
            if len(parts) < 2:
                return "Usage: /builder timeout <seconds>"
            builder.timeout(float(parts[1]))
            return f"Timeout set: {parts[1]}s"
        elif cmd == "build":
            try:
                req = builder.build()
                return f"method={req.method}  url={req.url}  timeout={req.timeout}"
            except BuilderError as e:
                return f"Error: {e}"
        elif cmd == "reset":
            builder.reset()
            return "Builder reset."
        return f"Unknown subcommand: {cmd}"

    async def strategy_handler(args: str) -> str:
        """Usage: /strategy <sort asc|desc <items...> | compress rle|none <text> | demo>"""
        from lidco.patterns.strategy import (
            Context, AscendingSortStrategy, DescendingSortStrategy,
            RLECompressionStrategy, NoCompressionStrategy,
        )
        parts = args.strip().split(maxsplit=2)
        if not parts:
            return "Usage: /strategy <sort asc|desc items | compress rle|none text | demo>"
        cmd = parts[0].lower()
        if cmd == "sort":
            if len(parts) < 3:
                return "Usage: /strategy sort <asc|desc> <item1 item2 ...>"
            order, items_str = parts[1].lower(), parts[2]
            items = items_str.split()
            ctx = Context()
            ctx.set_strategy(AscendingSortStrategy() if order == "asc" else DescendingSortStrategy())
            result = ctx.execute(items)
            return f"Sorted ({order}): {result}"
        elif cmd == "compress":
            if len(parts) < 3:
                return "Usage: /strategy compress <rle|none> <text>"
            algo, text = parts[1].lower(), parts[2]
            ctx = Context()
            ctx.set_strategy(RLECompressionStrategy() if algo == "rle" else NoCompressionStrategy())
            result = ctx.execute(text)
            return f"Result: {result!r}"
        elif cmd == "demo":
            ctx = Context(AscendingSortStrategy())
            asc = ctx.execute([3, 1, 4, 1, 5, 9])
            ctx.set_strategy(DescendingSortStrategy())
            desc = ctx.execute([3, 1, 4, 1, 5, 9])
            return f"asc={asc}\ndesc={desc}\nhistory={ctx.strategy_history}"
        return f"Unknown subcommand: {cmd}"

    async def template_handler(args: str) -> str:
        """Usage: /template <text <value> | numbers <n1 n2 ...> | report title | demo>"""
        from lidco.patterns.template_method import TextNormalizer, NumberPipeline, ReportGenerator
        parts = args.strip().split(maxsplit=1)
        if not parts:
            return "Usage: /template <text value | numbers n1 n2 | report title | demo>"
        cmd = parts[0].lower()
        rest = parts[1] if len(parts) > 1 else ""
        if cmd == "text":
            if not rest:
                return "Usage: /template text <value>"
            try:
                result = TextNormalizer().process(rest)
                return f"Normalized: {result!r}"
            except ValueError as e:
                return f"Error: {e}"
        elif cmd == "numbers":
            if not rest:
                return "Usage: /template numbers <n1 n2 ...>"
            try:
                numbers = [float(x) for x in rest.split()]
                result = NumberPipeline().process(numbers)
                return f"Processed: {result}"
            except Exception as e:
                return f"Error: {e}"
        elif cmd == "report":
            title = rest or "Untitled"
            gen = ReportGenerator(title)
            result = gen.process("Sample data")
            return result
        elif cmd == "demo":
            t = TextNormalizer().process("  Hello World  ")
            n = NumberPipeline().process([1, -2, 3, -4, 5])
            return f"text={t!r}\nnumbers={n}"
        return f"Unknown subcommand: {cmd}"

    async def decorator_pattern_handler(args: str) -> str:
        """Usage: /decorator-pattern <demo | wrap upper|prefix:X|suffix:X|cache|log text | chain>"""
        from lidco.patterns.decorator_pattern import (
            ConcreteComponent, UpperCaseDecorator, PrefixDecorator,
            SuffixDecorator, CachingDecorator, LoggingDecorator,
        )
        parts = args.strip().split(maxsplit=2)
        if not parts:
            return "Usage: /decorator-pattern <demo | wrap <decorators> <text>>"
        cmd = parts[0].lower()
        if cmd == "demo":
            comp = ConcreteComponent("hello")
            upper = UpperCaseDecorator(comp)
            prefixed = PrefixDecorator(upper, ">>> ")
            result = prefixed.operation()
            return f"original={comp.operation()!r}\nupper={upper.operation()!r}\nprefixed={result!r}\ndesc={prefixed.description}"
        elif cmd == "wrap":
            if len(parts) < 3:
                return "Usage: /decorator-pattern wrap <upper|prefix:X|suffix:X|cache|log> <text>"
            decs_str, text = parts[1], parts[2]
            comp = ConcreteComponent(text)
            current = comp
            for dec in decs_str.split(","):
                dec = dec.strip()
                if dec == "upper":
                    current = UpperCaseDecorator(current)
                elif dec.startswith("prefix:"):
                    current = PrefixDecorator(current, dec[7:])
                elif dec.startswith("suffix:"):
                    current = SuffixDecorator(current, dec[7:])
                elif dec == "cache":
                    current = CachingDecorator(current)
                elif dec == "log":
                    current = LoggingDecorator(current)
            return f"result={current.operation()!r}  desc={current.description}"
        elif cmd == "cache":
            if len(parts) < 2:
                return "Usage: /decorator-pattern cache <text>"
            text = parts[1] if len(parts) > 1 else "hello"
            comp = CachingDecorator(ConcreteComponent(text))
            comp.operation()
            comp.operation()
            return f"result={comp.operation()!r}  calls={comp.call_count}"
        return f"Unknown subcommand: {cmd}"

    registry.register(SlashCommand("builder", "HTTP request builder", builder_handler))
    registry.register(SlashCommand("strategy", "Strategy pattern algorithms", strategy_handler))
    registry.register(SlashCommand("template", "Template method data processing", template_handler))
    registry.register(SlashCommand("decorator-pattern", "Structural decorator pattern", decorator_pattern_handler))
