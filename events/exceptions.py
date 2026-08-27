from rest_framework.exceptions import APIException


class BaseCustomException(APIException):
    def __init__(self, detail, code):
        self.detail = {"detail": detail, "code": code}


class InvalidDateRangeException(BaseCustomException):
    status_code = 400


class InvalidCapacityException(BaseCustomException):
    status_code = 400


class CapacityTooLowException(BaseCustomException):
    status_code = 400


class ActiveEnrollmentsExistException(BaseCustomException):
    status_code = 409


class PermissionDeniedException(BaseCustomException):
    status_code = 403


class NotFoundException(BaseCustomException):
    status_code = 404


class InvalidQueryParameterException(BaseCustomException):
    status_code = 400


class EventStartedException(BaseCustomException):
    status_code = 400


class EventFullException(BaseCustomException):
    status_code = 409


class AlreadyEnrolledException(BaseCustomException):
    status_code = 400


class NotEnrolledException(BaseCustomException):
    status_code = 404


class AlreadyCanceledException(BaseCustomException):
    status_code = 400


class InvalidPeriodException(BaseCustomException):
    status_code = 400
