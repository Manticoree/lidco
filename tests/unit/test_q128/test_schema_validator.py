"""Tests for lidco.config.schema_validator."""
from lidco.config.schema_validator import SchemaValidator, ValidationError, ValidationResult


SCHEMA = {
    "name": {"type": "str", "required": True},
    "age": {"type": "int", "required": False, "default": 0},
    "active": {"type": "bool", "required": False, "default": False},
}


class TestValidationResult:
    def test_valid(self):
        r = ValidationResult(valid=True)
        assert r.valid is True
        assert r.error_count == 0

    def test_invalid_with_errors(self):
        e = ValidationError(field="name", message="required")
        r = ValidationResult(valid=False, errors=[e])
        assert r.error_count == 1


class TestSchemaValidator:
    def setup_method(self):
        self.v = SchemaValidator(SCHEMA)

    def test_valid_data(self):
        result = self.v.validate({"name": "Alice", "age": 30})
        assert result.valid is True

    def test_missing_required(self):
        result = self.v.validate({"age": 25})
        assert result.valid is False
        assert any(e.field == "name" for e in result.errors)

    def test_wrong_type(self):
        result = self.v.validate({"name": "Alice", "age": "not_an_int"})
        assert result.valid is False
        assert any(e.field == "age" for e in result.errors)

    def test_optional_field_missing_ok(self):
        result = self.v.validate({"name": "Bob"})
        assert result.valid is True

    def test_coerce_applies_defaults(self):
        data = {"name": "Alice"}
        coerced = self.v.coerce(data)
        assert coerced["age"] == 0
        assert coerced["active"] is False

    def test_coerce_type_int(self):
        data = {"name": "Alice", "age": "30"}
        coerced = self.v.coerce(data)
        assert coerced["age"] == 30
        assert isinstance(coerced["age"], int)

    def test_coerce_type_str(self):
        v = SchemaValidator({"x": {"type": "str"}})
        coerced = v.coerce({"x": 42})
        assert coerced["x"] == "42"

    def test_required_fields(self):
        fields = self.v.required_fields()
        assert "name" in fields
        assert "age" not in fields

    def test_empty_data_required_fails(self):
        result = self.v.validate({})
        assert result.valid is False

    def test_no_required_fields(self):
        v = SchemaValidator({"x": {"type": "str"}})
        assert v.required_fields() == []

    def test_multiple_type_errors(self):
        v = SchemaValidator({
            "a": {"type": "int", "required": True},
            "b": {"type": "bool", "required": True},
        })
        result = v.validate({"a": "not_int", "b": "not_bool"})
        assert result.error_count == 2

    def test_coerce_preserves_existing_correct_types(self):
        data = {"name": "Bob", "age": 25, "active": True}
        coerced = self.v.coerce(data)
        assert coerced["age"] == 25
        assert coerced["active"] is True

    def test_validate_with_extra_fields(self):
        result = self.v.validate({"name": "Alice", "extra": "ignored"})
        assert result.valid is True

    def test_coerce_does_not_mutate_input(self):
        data = {"name": "Alice"}
        _ = self.v.coerce(data)
        assert "age" not in data

    def test_empty_schema(self):
        v = SchemaValidator({})
        result = v.validate({"anything": "goes"})
        assert result.valid is True

    def test_validation_error_message(self):
        result = self.v.validate({"age": 5})
        err = next(e for e in result.errors if e.field == "name")
        assert "required" in err.message.lower() or "name" in err.message.lower()

    def test_coerce_int_fails_gracefully(self):
        data = {"name": "Alice", "age": "not_a_number_at_all_!!!"}
        coerced = self.v.coerce(data)
        # Should remain unchanged on failed coerce
        assert coerced["age"] == "not_a_number_at_all_!!!"

    def test_required_fields_multiple(self):
        v = SchemaValidator({
            "a": {"required": True},
            "b": {"required": True},
            "c": {"required": False},
        })
        rf = v.required_fields()
        assert set(rf) == {"a", "b"}
