class NotFoundError(Exception):
    """The requested resource does not exist. Mapped to HTTP 404."""


class ConflictError(Exception):
    """The request conflicts with the current state of the data. Mapped to HTTP 409."""
