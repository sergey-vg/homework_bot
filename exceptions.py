class PraktikumAPIError(Exception):
    """Базовое исключение для ошибок API Практикум."""

    pass


class TokenError(PraktikumAPIError):
    """Исключение для ошибок, связанных с токенами."""

    pass


class APIResponseError(PraktikumAPIError):
    """Исключение для ошибок в ответе от API."""

    pass
