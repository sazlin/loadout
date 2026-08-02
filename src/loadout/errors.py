class LoadoutError(Exception):
    def __init__(self, message: str, code: int = 2):
        super().__init__(message)
        self.code = code


class ValidationError(LoadoutError):
    def __init__(self, message: str):
        super().__init__(message, code=2)


class DriftError(LoadoutError):
    def __init__(self, message: str):
        super().__init__(message, code=1)


class FetchError(LoadoutError):
    def __init__(self, message: str):
        super().__init__(message, code=3)
