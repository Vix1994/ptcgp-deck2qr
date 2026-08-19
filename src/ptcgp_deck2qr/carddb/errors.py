"""Explicit errors raised at the external database boundary."""


class DatabaseError(ValueError):
    """Base class for invalid or unusable external database releases."""


class DatabaseSchemaError(DatabaseError):
    """The external database does not satisfy the documented schema contract."""


class IndexSourceMismatch(DatabaseError):
    """A generated fingerprint index belongs to a different database release."""
