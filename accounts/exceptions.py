from rest_framework.exceptions import APIException


class BaseCustomException(APIException):
    def __init__(self, detail, code):
        self.detail = {"detail": detail, "code": code}


class InvalidOTPException(BaseCustomException):
    status_code = 400


class CooldownActiveException(BaseCustomException):
    status_code = 429


class EmailAlreadyRegisteredException(BaseCustomException):
    status_code = 409


class OTPExpiredException(BaseCustomException):
    status_code = 400


class OTPMaxAttemptsException(BaseCustomException):
    status_code = 400


class AlreadyVerifiedException(BaseCustomException):
    status_code = 400


class InvalidCredentialsException(BaseCustomException):
    status_code = 401


class EmailNotVerifiedException(BaseCustomException):
    status_code = 403
