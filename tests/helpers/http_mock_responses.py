# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Mock Responses for Unit Testing

This module contains mock response classes used in unit testing. These classes are designed to simulate the behavior of real responses
from asynchronous HTTP requests, specifically for use with the aiohttp library. The mocks facilitate testing of async functions and methods
by providing controlled responses, including both successful responses and errors.

Classes:
- MockResponse_1: Simulates the response object returned by aiohttp.ClientSession().get() for successful HTTP requests.
- MockResponse: Simulates an HTTP response object for testing error handling and other response scenarios.

These mock classes are utilized in the unit tests of async functions to ensure proper handling of various HTTP responses
without the need for actual network calls, thus enabling more efficient and isolated testing.
"""


class MockResponse_download_faq:
    def __init__(self, text, status):
        self._text = text
        self.status = status

    async def text(self):
        return self._text

    async def __aexit__(self, exc_type, exc, tb):
        pass

    async def __aenter__(self):
        return self


class MockResponse_faq_entries:
    """Simulates the response object returned by aiohttp.ClientSession().get().

    Parameters
    ----------
    json_data : dict
        The JSON data to return when the json() method is called.
    status : int
        The HTTP status code to return.

    Methods
    -------
    async json():
        Returns the JSON data.
    async text():
        Returns the JSON data as a string.

    """

    def __init__(self, json_data, status):
        self.json_data = json_data
        self.status = status

    async def json(self):
        return self.json_data

    async def text(self):
        return str(self.json_data)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        pass
