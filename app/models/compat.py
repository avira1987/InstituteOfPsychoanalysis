"""Database compatibility layer - abstracts PostgreSQL-specific types for SQLite support."""

import uuid
from sqlalchemy import String, JSON, TypeDecorator


class GUID(TypeDecorator):
    """Platform-independent UUID type. Uses String(36) storage."""
    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            if isinstance(value, uuid.UUID):
                return str(value)
            return str(value)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            if not isinstance(value, uuid.UUID):
                return uuid.UUID(value)
        return value


# Use JSON type (works with both PostgreSQL JSONB and SQLite JSON)
JSONType = JSON
