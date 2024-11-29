class PraktikumAPIError(Exception):
    """Базовое исключение для ошибок API Практикум."""


class TokenError(PraktikumAPIError):
    """Исключение для ошибок, связанных с токенами."""


class APIResponseError(PraktikumAPIError):
    """Исключение для ошибок в ответе от API."""
