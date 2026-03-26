"""Tests for src/lidco/cqrs/bus.py — CommandBus, QueryBus."""
import pytest
from lidco.cqrs.bus import (
    CommandBus, QueryBus, CommandResult,
    CommandNotRegisteredError, QueryNotRegisteredError,
)


class CreateUserCommand:
    def __init__(self, name: str):
        self.name = name


class GetUserQuery:
    def __init__(self, user_id: str):
        self.user_id = user_id


class TestCommandBus:
    def test_register_and_dispatch(self):
        bus = CommandBus()
        bus.register(lambda cmd: f"user:{cmd.name}", name="CreateUserCommand")
        result = bus.dispatch(CreateUserCommand("Alice"))
        assert result.success is True
        assert result.data == "user:Alice"

    def test_dispatch_unregistered_raises(self):
        bus = CommandBus()
        with pytest.raises(CommandNotRegisteredError) as exc:
            bus.dispatch(CreateUserCommand("Alice"))
        assert exc.value.command_name == "CreateUserCommand"

    def test_handler_exception_returns_failure(self):
        bus = CommandBus()
        bus.register(lambda cmd: (_ for _ in ()).throw(ValueError("oops")),
                     name="CreateUserCommand")
        result = bus.dispatch(CreateUserCommand("Alice"))
        assert result.success is False
        assert "oops" in result.error

    def test_unregister(self):
        bus = CommandBus()
        bus.register(lambda cmd: "ok", name="CreateUserCommand")
        assert bus.unregister("CreateUserCommand") is True
        with pytest.raises(CommandNotRegisteredError):
            bus.dispatch(CreateUserCommand("Alice"))

    def test_unregister_nonexistent(self):
        bus = CommandBus()
        assert bus.unregister("NoSuchCommand") is False

    def test_registered_commands(self):
        bus = CommandBus()
        bus.register(lambda cmd: None, name="CmdA")
        bus.register(lambda cmd: None, name="CmdB")
        names = bus.registered_commands()
        assert "CmdA" in names
        assert "CmdB" in names
        assert names == sorted(names)

    def test_middleware_called(self):
        bus = CommandBus()
        log = []

        def mw(cmd, next_fn):
            log.append("before")
            result = next_fn()
            log.append("after")
            return result

        bus.use(mw)
        bus.register(lambda cmd: "done", name="CreateUserCommand")
        bus.dispatch(CreateUserCommand("Alice"))
        assert log == ["before", "after"]

    def test_middleware_can_short_circuit(self):
        bus = CommandBus()
        bus.use(lambda cmd, next_fn: "short_circuit")
        bus.register(lambda cmd: "real", name="CreateUserCommand")
        result = bus.dispatch(CreateUserCommand("Alice"))
        assert result.data == "short_circuit"

    def test_command_result_dataclass(self):
        r = CommandResult(success=True, data=42)
        assert r.success is True
        assert r.data == 42


class TestQueryBus:
    def test_register_and_query(self):
        bus = QueryBus()
        bus.register(lambda q: {"id": q.user_id}, name="GetUserQuery")
        result = bus.query(GetUserQuery("u1"))
        assert result == {"id": "u1"}

    def test_query_unregistered_raises(self):
        bus = QueryBus()
        with pytest.raises(QueryNotRegisteredError) as exc:
            bus.query(GetUserQuery("u1"))
        assert exc.value.query_name == "GetUserQuery"

    def test_unregister(self):
        bus = QueryBus()
        bus.register(lambda q: None, name="GetUserQuery")
        assert bus.unregister("GetUserQuery") is True
        with pytest.raises(QueryNotRegisteredError):
            bus.query(GetUserQuery("u1"))

    def test_unregister_nonexistent(self):
        bus = QueryBus()
        assert bus.unregister("NoSuchQuery") is False

    def test_registered_queries(self):
        bus = QueryBus()
        bus.register(lambda q: None, name="QueryA")
        bus.register(lambda q: None, name="QueryB")
        names = bus.registered_queries()
        assert names == sorted(names)
        assert "QueryA" in names

    def test_explicit_name_override(self):
        bus = QueryBus()
        bus.register(lambda q: "ok", name="custom_name")
        result = bus.query(GetUserQuery("u1"), name="custom_name")
        assert result == "ok"
