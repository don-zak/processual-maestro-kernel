class CGTError(Exception):
    """Base exception for cgtlib."""


class ValidationError(CGTError):
    """Raised when inputs violate cgtlib constraints."""
