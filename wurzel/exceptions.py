# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""contains custom logged exceptions."""

import logging

log = logging.getLogger(__name__)


class LoggedCustomException(Exception):
    """custom logged exception class."""

    def __init__(self, message):
        """Constructor."""
        self.message = message
        super().__init__(message)
        log.exception(self)

    def __repr__(self) -> str:
        return f"{str(self.__class__.__name__)}: {self.message}"

    def __str__(self) -> str:
        return self.__repr__()


class EnvSettingsError(ValueError):
    """Special Error for env related errors in regards to TypedStep settings."""


class BadResponse(LoggedCustomException):
    """raises if an HTTP api does not return 200."""


class StepFailed(LoggedCustomException):
    """raised when a step fails unintented."""


class InvalidCountryCodeException(LoggedCustomException):
    """raised when countryCode in url path is not recognized
    or not in accordance to ISO_3166.
    """


class ContractFailedException(LoggedCustomException):
    """raised when a data contract is not fulfilled."""


class StaticTypeError(ContractFailedException, TypeError):
    """raised if static type hinting are wrong."""


class ConvertFailed(LoggedCustomException):
    """raised when html2md fails."""


class CLIException(LoggedCustomException):
    """raised when the given string is not a valid Callable Pipeline."""


class NoPreviousCollection(LoggedCustomException):
    """raised when milvus does not contain previous collection."""


class MarkdownException(LoggedCustomException):
    """raised when Markdown libary complains."""


class CustomQdrantException(LoggedCustomException):
    """raised when qdrant status is not fine."""


class SplittException(LoggedCustomException):
    """Document had to have children."""


class EmbeddingException(LoggedCustomException):
    """The EmbeddingService returned data causing errors."""


class EmbeddingAPIException(LoggedCustomException):
    """The EmbeddingServiceAPI experienced an Error."""


class UnrecoverableFatalException(LoggedCustomException):
    """Raised when the application encountered a problem that cannot be recovered."""


class MarkdownConvertFailed(LoggedCustomException):
    """raised when html2md fails."""


class InvalidPlatform(LoggedCustomException):
    """raised when Platform is not supported."""
