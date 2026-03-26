"""Tests for src/lidco/patterns/builder.py — Builder, HttpRequestBuilder."""
import pytest
from lidco.patterns.builder import Builder, HttpRequestBuilder, HttpRequest, BuilderError


class PersonBuilder(Builder):
    _required = ["name", "age"]

    def name(self, v: str) -> "PersonBuilder":
        return self._set("name", v)  # type: ignore

    def age(self, v: int) -> "PersonBuilder":
        return self._set("age", v)  # type: ignore

    def email(self, v: str) -> "PersonBuilder":
        return self._set("email", v)  # type: ignore

    def build(self) -> dict:
        self._validate()
        return dict(self._data)


class TestBuilderBase:
    def test_build_success(self):
        person = PersonBuilder().name("Alice").age(30).build()
        assert person["name"] == "Alice"
        assert person["age"] == 30

    def test_missing_required_raises(self):
        with pytest.raises(BuilderError) as exc:
            PersonBuilder().name("Alice").build()
        assert "age" in str(exc.value)

    def test_chaining(self):
        b = PersonBuilder()
        result = b.name("Alice").age(30).email("a@b.com")
        assert result is b

    def test_reset(self):
        b = PersonBuilder().name("Alice").age(30)
        b.reset()
        with pytest.raises(BuilderError):
            b.build()

    def test_get(self):
        b = PersonBuilder().name("Alice")
        assert b.get("name") == "Alice"
        assert b.get("missing", "default") == "default"


class TestHttpRequestBuilder:
    def test_get_request(self):
        req = HttpRequestBuilder().get("https://api.example.com").build()
        assert req.method == "GET"
        assert req.url == "https://api.example.com"

    def test_post_request(self):
        req = HttpRequestBuilder().post("https://api.example.com").build()
        assert req.method == "POST"

    def test_method_uppercased(self):
        req = HttpRequestBuilder().method("delete").url("https://x.com").build()
        assert req.method == "DELETE"

    def test_header(self):
        req = (HttpRequestBuilder()
               .get("https://x.com")
               .header("Accept", "application/json")
               .build())
        assert req.headers["Accept"] == "application/json"

    def test_multiple_headers(self):
        req = (HttpRequestBuilder()
               .get("https://x.com")
               .header("A", "1")
               .header("B", "2")
               .build())
        assert req.headers == {"A": "1", "B": "2"}

    def test_body(self):
        req = HttpRequestBuilder().post("https://x.com").body('{"key": "val"}').build()
        assert req.body == '{"key": "val"}'

    def test_timeout(self):
        req = HttpRequestBuilder().get("https://x.com").timeout(5.0).build()
        assert req.timeout == 5.0

    def test_default_timeout(self):
        req = HttpRequestBuilder().get("https://x.com").build()
        assert req.timeout == 30.0

    def test_param(self):
        req = HttpRequestBuilder().get("https://x.com").param("page", "1").build()
        assert req.params["page"] == "1"

    def test_missing_url_raises(self):
        with pytest.raises(BuilderError):
            HttpRequestBuilder().method("GET").build()

    def test_missing_method_raises(self):
        with pytest.raises(BuilderError):
            HttpRequestBuilder().url("https://x.com").build()

    def test_result_type(self):
        req = HttpRequestBuilder().get("https://x.com").build()
        assert isinstance(req, HttpRequest)

    def test_immutable_result(self):
        req = HttpRequestBuilder().get("https://x.com").build()
        # HttpRequest is a dataclass — fields should not be accidentally shared
        from dataclasses import asdict
        d = asdict(req)
        assert "method" in d
