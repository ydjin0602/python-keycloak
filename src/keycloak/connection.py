#
# The MIT License (MIT)
#
# Copyright (C) 2017 Marcos Pereira <marcospereira.mpj@gmail.com>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in
# the Software without restriction, including without limitation the rights to
# use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
# the Software, and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
# FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
# COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
# IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

"""Connection manager module."""

from __future__ import annotations

try:
    from urllib.parse import urljoin
except ImportError:  # pragma: no cover
    from urlparse import urljoin

import httpx
import requests
from httpx import Response as AsyncResponse
from requests import Response
from requests.adapters import HTTPAdapter

from .exceptions import KeycloakConnectionError


class ConnectionManager:
    """
    Represents a simple server connection.

    :param base_url: The server URL.
    :type base_url: str
    :param headers: The header parameters of the requests to the server.
    :type headers: dict
    :param timeout: Timeout to use for requests to the server.
    :type timeout: int
    :param verify: Boolean value to enable or disable certificate validation or a string
        containing a path to a CA bundle to use
    :type verify: Union[bool,str]
    :param proxies: The proxies servers requests is sent by.
    :type proxies: dict
    :param cert: An SSL certificate used by the requested host to authenticate the client.
        Either a path to an SSL certificate file, or two-tuple of
        (certificate file, key file).
    :type cert: Union[str,Tuple[str,str]]
    :param max_retries: The total number of times to retry HTTP requests.
    :type max_retries: int
    """

    def __init__(
        self,
        base_url: str,
        headers: dict | None = None,
        timeout: int = 60,
        verify: bool = True,
        proxies: dict | None = None,
        cert: str | tuple | None = None,
        max_retries: int = 1,
    ) -> None:
        """
        Init method.

        :param base_url: The server URL.
        :type base_url: str
        :param headers: The header parameters of the requests to the server.
        :type headers: dict
        :param timeout: Timeout to use for requests to the server.
        :type timeout: int
        :param verify: Boolean value to enable or disable certificate validation or a string
            containing a path to a CA bundle to use
        :type verify: Union[bool,str]
        :param proxies: The proxies servers requests is sent by.
        :type proxies: dict
        :param cert: An SSL certificate used by the requested host to authenticate the client.
            Either a path to an SSL certificate file, or two-tuple of
            (certificate file, key file).
        :type cert: Union[str,Tuple[str,str]]
        :param max_retries: The total number of times to retry HTTP requests.
        :type max_retries: int
        """
        self.base_url = base_url
        self.headers = headers
        self.timeout = timeout
        self.verify = verify
        self.cert = cert
        self._s = requests.Session()
        self._s.auth = lambda x: x  # don't let requests add auth headers

        # retry once to reset connection with Keycloak after  tomcat's ConnectionTimeout
        # see https://github.com/marcospereirampj/python-keycloak/issues/36
        for protocol in ("https://", "http://"):
            adapter = HTTPAdapter(max_retries=max_retries)
            # adds POST to retry whitelist
            allowed_methods = set(adapter.max_retries.allowed_methods)
            allowed_methods.add("POST")
            adapter.max_retries.allowed_methods = frozenset(allowed_methods)

            self._s.mount(protocol, adapter)

        if proxies:
            self._s.proxies.update(proxies)

        self.async_s = httpx.AsyncClient(verify=verify, mounts=proxies, cert=cert)
        self.async_s.auth = None  # don't let requests add auth headers
        self.async_s.transport = httpx.AsyncHTTPTransport(retries=1)

    async def aclose(self) -> None:
        """Close the async connection on delete."""
        if hasattr(self, "_s"):
            await self.async_s.aclose()

    def __del__(self) -> None:
        """Del method."""
        if hasattr(self, "_s"):
            self._s.close()

    @property
    def base_url(self) -> str:
        """
        Return base url in use for requests to the server.

        :returns: Base URL
        :rtype: str
        """
        return self._base_url

    @base_url.setter
    def base_url(self, value: str) -> None:
        self._base_url = value

    @property
    def timeout(self) -> int:
        """
        Return timeout in use for request to the server.

        :returns: Timeout
        :rtype: int
        """
        return self._timeout

    @timeout.setter
    def timeout(self, value: int) -> None:
        self._timeout = value

    @property
    def verify(self) -> bool:
        """
        Return verify in use for request to the server.

        :returns: Verify indicator
        :rtype: bool
        """
        return self._verify

    @verify.setter
    def verify(self, value: bool) -> None:
        self._verify = value

    @property
    def cert(self) -> str | tuple:
        """
        Return client certificates in use for request to the server.

        :returns: Client certificate
        :rtype: Union[str,Tuple[str,str]]
        """
        return self._cert

    @cert.setter
    def cert(self, value: str | tuple) -> None:
        self._cert = value

    @property
    def headers(self) -> dict:
        """
        Return header request to the server.

        :returns: Request headers
        :rtype: dict
        """
        return self._headers

    @headers.setter
    def headers(self, value: dict) -> None:
        self._headers = value or {}

    def param_headers(self, key: str) -> str | None:
        """
        Return a specific header parameter.

        :param key: Header parameters key.
        :type key: str
        :returns: If the header parameters exist, return its value.
        :rtype: str
        """
        return self.headers.get(key)

    def clean_headers(self) -> None:
        """Clear header parameters."""
        self.headers = {}

    def exist_param_headers(self, key: str) -> bool:
        """
        Check if the parameter exists in the header.

        :param key: Header parameters key.
        :type key: str
        :returns: If the header parameters exist, return True.
        :rtype: bool
        """
        return self.param_headers(key) is not None

    def add_param_headers(self, key: str, value: str) -> None:
        """
        Add a single parameter inside the header.

        :param key: Header parameters key.
        :type key: str
        :param value: Value to be added.
        :type value: str
        """
        self.headers[key] = value

    def del_param_headers(self, key: str) -> None:
        """
        Remove a specific parameter.

        :param key: Key of the header parameters.
        :type key: str
        """
        self.headers.pop(key, None)

    def raw_get(self, path: str, **kwargs: dict) -> Response:
        """
        Submit get request to the path.

        :param path: Path for request.
        :type path: str
        :param kwargs: Additional arguments
        :type kwargs: dict
        :returns: Response the request.
        :rtype: Response
        :raises KeycloakConnectionError: HttpError Can't connect to server.
        """
        try:
            return self._s.get(
                urljoin(self.base_url, path),
                params=kwargs,
                headers=self.headers,
                timeout=self.timeout,
                verify=self.verify,
                cert=self.cert,
            )
        except Exception as e:
            raise KeycloakConnectionError(repr(e)) from e

    def raw_post(self, path: str, data: dict, **kwargs: dict) -> Response:
        """
        Submit post request to the path.

        :param path: Path for request.
        :type path: str
        :param data: Payload for request.
        :type data: dict
        :param kwargs: Additional arguments
        :type kwargs: dict
        :returns: Response the request.
        :rtype: Response
        :raises KeycloakConnectionError: HttpError Can't connect to server.
        """
        try:
            return self._s.post(
                urljoin(self.base_url, path),
                params=kwargs,
                data=data,
                headers=self.headers,
                timeout=self.timeout,
                verify=self.verify,
                cert=self.cert,
            )
        except Exception as e:
            raise KeycloakConnectionError(repr(e)) from e

    def raw_put(self, path: str, data: dict, **kwargs: dict) -> Response:
        """
        Submit put request to the path.

        :param path: Path for request.
        :type path: str
        :param data: Payload for request.
        :type data: dict
        :param kwargs: Additional arguments
        :type kwargs: dict
        :returns: Response the request.
        :rtype: Response
        :raises KeycloakConnectionError: HttpError Can't connect to server.
        """
        try:
            return self._s.put(
                urljoin(self.base_url, path),
                params=kwargs,
                data=data,
                headers=self.headers,
                timeout=self.timeout,
                verify=self.verify,
                cert=self.cert,
            )
        except Exception as e:
            raise KeycloakConnectionError(repr(e)) from e

    def raw_delete(self, path: str, data: dict | None = None, **kwargs: dict) -> Response:
        """
        Submit delete request to the path.

        :param path: Path for request.
        :type path: str
        :param data: Payload for request.
        :type data: dict | None
        :param kwargs: Additional arguments
        :type kwargs: dict
        :returns: Response the request.
        :rtype: Response
        :raises KeycloakConnectionError: HttpError Can't connect to server.
        """
        try:
            return self._s.delete(
                urljoin(self.base_url, path),
                params=kwargs,
                data=data or {},
                headers=self.headers,
                timeout=self.timeout,
                verify=self.verify,
                cert=self.cert,
            )
        except Exception as e:
            raise KeycloakConnectionError(repr(e)) from e

    async def a_raw_get(self, path: str, **kwargs: dict) -> AsyncResponse:
        """
        Submit get request to the path.

        :param path: Path for request.
        :type path: str
        :param kwargs: Additional arguments
        :type kwargs: dict
        :returns: Response the request.
        :rtype: Response
        :raises KeycloakConnectionError: HttpError Can't connect to server.
        """
        try:
            return await self.async_s.get(
                urljoin(self.base_url, path),
                params=self._filter_query_params(kwargs),
                headers=self.headers,
                timeout=self.timeout,
            )
        except Exception as e:
            raise KeycloakConnectionError(repr(e)) from e

    async def a_raw_post(self, path: str, data: dict, **kwargs: dict) -> AsyncResponse:
        """
        Submit post request to the path.

        :param path: Path for request.
        :type path: str
        :param data: Payload for request.
        :type data: dict
        :param kwargs: Additional arguments
        :type kwargs: dict
        :returns: Response the request.
        :rtype: Response
        :raises KeycloakConnectionError: HttpError Can't connect to server.
        """
        try:
            return await self.async_s.request(
                method="POST",
                url=urljoin(self.base_url, path),
                params=self._filter_query_params(kwargs),
                data=data,
                headers=self.headers,
                timeout=self.timeout,
            )
        except Exception as e:
            raise KeycloakConnectionError(repr(e)) from e

    async def a_raw_put(self, path: str, data: dict, **kwargs: dict) -> AsyncResponse:
        """
        Submit put request to the path.

        :param path: Path for request.
        :type path: str
        :param data: Payload for request.
        :type data: dict
        :param kwargs: Additional arguments
        :type kwargs: dict
        :returns: Response the request.
        :rtype: Response
        :raises KeycloakConnectionError: HttpError Can't connect to server.
        """
        try:
            return await self.async_s.put(
                urljoin(self.base_url, path),
                params=self._filter_query_params(kwargs),
                data=data,
                headers=self.headers,
                timeout=self.timeout,
            )
        except Exception as e:
            raise KeycloakConnectionError(repr(e)) from e

    async def a_raw_delete(
        self,
        path: str,
        data: dict | None = None,
        **kwargs: dict,
    ) -> AsyncResponse:
        """
        Submit delete request to the path.

        :param path: Path for request.
        :type path: str
        :param data: Payload for request.
        :type data: dict | None
        :param kwargs: Additional arguments
        :type kwargs: dict
        :returns: Response the request.
        :rtype: Response
        :raises KeycloakConnectionError: HttpError Can't connect to server.
        """
        try:
            return await self.async_s.request(
                method="DELETE",
                url=urljoin(self.base_url, path),
                data=data or {},
                params=self._filter_query_params(kwargs),
                headers=self.headers,
                timeout=self.timeout,
            )
        except Exception as e:
            raise KeycloakConnectionError(repr(e)) from e

    @staticmethod
    def _filter_query_params(query_params: dict) -> dict:
        """
        Explicitly filter query params with None values for compatibility.

        Httpx and requests differ in the way they handle query params with the value None,
        requests does not include params with the value None while httpx includes them as-is.

        :param query_params: the query params
        :type query_params: dict
        :returns: the filtered query params
        :rtype: dict
        """
        return {k: v for k, v in query_params.items() if v is not None}
