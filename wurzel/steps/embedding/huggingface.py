# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""contains Embedding Manager."""

from json.decoder import JSONDecodeError
from logging import getLogger
from re import Pattern as RegexPattern
from typing import Literal, Union

import requests
from langchain_core.embeddings import Embeddings
from pydantic import validate_call
from pydantic_core import Url

from wurzel.exceptions import (
    EmbeddingAPIException,
    EmbeddingException,
    UnrecoverableFatalException,
)

log = getLogger(__name__)


@validate_call
def _url_with_path(base: Url, path: str) -> Url:
    return Url.build(
        scheme=base.scheme,
        username=base.username,
        password=base.password,
        host=base.host,
        port=base.port,
        path=path,
        query=base.query,
        fragment=base.fragment,
    )


class HuggingFaceInferenceAPIEmbeddings(Embeddings):
    """Embed texts using the HuggingFace API.

    Requires a HuggingFace interface deployed as service
    """

    _timeout: int = 10
    embedding_url: Url
    info_url: Url
    _last_model: str
    _on_model_change: callable = None
    _normalize: bool = False

    @validate_call
    def __init__(self, url: Url, normalize: bool = False):
        self._normalize = normalize
        self.embedding_url = _url_with_path(url, "embed")
        self.info_url = _url_with_path(url, "info")
        self._last_model = None
        self._update_model_history(self.get_info()["model_id"])

    def _update_model_history(self, model: str) -> bool:
        """Updates internal model history if model name is new.

        Args:
            model (str): string name/ path of model

        Returns:
            bool: has the model changed

        """
        model_name = model.strip("/").split("/")[-1]
        log.info(f"Model history: name={model_name}")
        if self._last_model is None or model_name != self._last_model:
            self._last_model = model_name
            return True
        return False

    @validate_call
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Get the embeddings for a list of texts."""
        return [self.embed_query(text) for text in texts]

    def __make_request(self, url: Url, json_body: dict, method: Union[Literal["post"], Literal["get"]]) -> dict:
        """Creates a request, tries to parse json.

        Args:
            url (str)
            json_body (dict): body to send

        Raises:
            EmbeddingAPIException: after timeout
            EmbeddingAPIException: invalid json
            EmbeddingAPIException: invalid statuscode

        Returns:
            dict: parsed response

        """
        try:
            response = requests.request(method, url, json=json_body, timeout=self._timeout)
        except (requests.exceptions.ConnectTimeout, requests.exceptions.Timeout) as err:
            raise EmbeddingAPIException(f"timed out after {self._timeout}") from err
        except requests.ConnectionError as err:
            raise EmbeddingAPIException("Connection Error") from err
        if response.status_code != 200:
            raise EmbeddingAPIException(f"failed, invalid status_code {response.status_code}")
        try:
            resp_dict = response.json()
        except JSONDecodeError as err:
            raise EmbeddingAPIException(f"failed due to invalid json {response.content}") from err

        return resp_dict

    def _request_embed_query(self, text: str) -> dict:
        return self.__make_request(
            self.embedding_url,
            {"inputs": text, "normalize": self._normalize},
            method="post",
        )

    @validate_call
    def embed_query(self, text: str) -> list[float]:
        """Compute query embeddings using a HuggingFace transformer model.

        Args:
            text: The text to embed.

        Returns:
            Embeddings for the text.

        """
        response = self._request_embed_query(text)
        try:
            value = response[0]
        except (KeyError, IndexError) as err:
            raise EmbeddingException(
                f"Response invalid Structure of received dict is incorrect: {response} should contain a list with one entry"
            ) from err
        return value

    def get_info(self):
        """Returns the infos of the model, described here:
        https://huggingface.github.io/text-embeddings-inference/#/.
        """
        response_model_key = "model_id"
        resp_dict = self.__make_request(self.info_url, None, method="get")
        if response_model_key not in resp_dict:
            raise EmbeddingException(f"Response invalid format {self.info_url} {resp_dict}requires {response_model_key}")
        return resp_dict


class PrefixedAPIEmbeddings(HuggingFaceInferenceAPIEmbeddings):
    """E5 and other models need a prefix within the input."""

    prefix: str = ""
    # Mapping function that should return None if it was not found
    prefix_mapping: dict[RegexPattern, str]

    @validate_call
    def __init__(self, url: Url, prefix_mapping: dict[RegexPattern, str]):
        super().__init__(url)
        self.prefix_mapping = prefix_mapping
        self.update_prefix()
        self._on_model_change = self.update_prefix

    @validate_call
    # overrides
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Get the embeddings for a list of texts."""
        texts = [f"{self.prefix}{text}" for text in texts]
        embedding_response = super().embed_documents(texts)
        return embedding_response

    def update_prefix(self):
        """Updates prompt/ embedding prefix used internally in every embedded request.

        Raises:
            UnrecoverableFatalException: no prefix-definition for a model was found

        """
        for regex, prefix in self.prefix_mapping.items():
            if regex.search(self._last_model):
                self.prefix = prefix
                log.info(f"Using prefix={prefix}")
                return
        raise UnrecoverableFatalException(
            f"Tried to get prefix for {self._last_model}:" + f"No match found in {self.prefix_mapping.keys()}"
        )
