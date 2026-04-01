"""Tests for BatchOptimizer."""

from lidco.economics.batch_optimizer import (
    BatchGroup,
    BatchOptimizer,
    BatchRequest,
    BatchResult,
)


class TestBatchOptimizer:
    def test_add_request(self):
        opt = BatchOptimizer()
        req = BatchRequest(id="1", content="hello")
        opt.add_request(req)
        assert len(opt._requests) == 1

    def test_group_requests_by_group_field(self):
        opt = BatchOptimizer()
        opt.add_request(BatchRequest(id="1", content="a", group="alpha"))
        opt.add_request(BatchRequest(id="2", content="b", group="alpha"))
        opt.add_request(BatchRequest(id="3", content="c", group="beta"))
        groups = opt.group_requests()
        names = {g.name for g in groups}
        assert names == {"alpha", "beta"}
        alpha = next(g for g in groups if g.name == "alpha")
        assert len(alpha.requests) == 2

    def test_group_requests_merges_shared_context(self):
        opt = BatchOptimizer()
        ctx = {"project": "lidco", "lang": "python"}
        opt.add_request(BatchRequest(id="1", content="a", context=ctx, group="g"))
        opt.add_request(BatchRequest(id="2", content="b", context={"project": "lidco", "lang": "rust"}, group="g"))
        groups = opt.group_requests()
        g = groups[0]
        assert g.shared_context == {"project": "lidco"}

    def test_deduplicate_context_across_groups(self):
        opt = BatchOptimizer()
        g1 = BatchGroup(name="a", requests=(), shared_context={"project": "lidco", "x": "1"})
        g2 = BatchGroup(name="b", requests=(), shared_context={"project": "lidco", "y": "2"})
        deduped = opt.deduplicate_context([g1, g2])
        # "project" was common, should be removed from individual groups
        for g in deduped:
            assert "project" not in g.shared_context

    def test_optimize_returns_result(self):
        opt = BatchOptimizer()
        opt.add_request(BatchRequest(id="1", content="a", context={"k": "v"}, group="g1"))
        opt.add_request(BatchRequest(id="2", content="b", context={"k": "v"}, group="g2"))
        result = opt.optimize()
        assert isinstance(result, BatchResult)
        assert result.total_requests == 2
        assert len(result.groups) == 2

    def test_clear_resets_state(self):
        opt = BatchOptimizer()
        opt.add_request(BatchRequest(id="1", content="a"))
        opt.optimize()
        opt.clear()
        assert len(opt._requests) == 0
        assert len(opt._results) == 0

    def test_summary(self):
        opt = BatchOptimizer()
        s = opt.summary()
        assert "Requests: 0" in s
        opt.add_request(BatchRequest(id="1", content="a"))
        opt.optimize()
        s = opt.summary()
        assert "Optimizations run: 1" in s

    def test_priority_sorting_within_group(self):
        opt = BatchOptimizer()
        opt.add_request(BatchRequest(id="1", content="low", priority=1, group="g"))
        opt.add_request(BatchRequest(id="2", content="high", priority=10, group="g"))
        opt.add_request(BatchRequest(id="3", content="mid", priority=5, group="g"))
        groups = opt.group_requests()
        g = groups[0]
        priorities = [r.priority for r in g.requests]
        assert priorities == [10, 5, 1]
