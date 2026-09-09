class NotFoundError(Exception):
    pass


class ConflictError(Exception):
    pass


class AuthenticationError(Exception):
    pass


class ForbiddenError(Exception):
    pass


class TooManyRequestsError(Exception):
    pass


class ServiceUnavailableError(Exception):
    pass
