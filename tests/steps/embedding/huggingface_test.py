# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import re

import pytest
import requests_mock
from pydantic_core import Url

from wurzel.utils import HAS_LANGCHAIN_CORE, HAS_REQUESTS

if not HAS_LANGCHAIN_CORE or not HAS_REQUESTS:
    pytest.skip("Embedding dependencies (langchain-core, requests) are not available", allow_module_level=True)

from tests.steps.embedding.conftest import (
    GET_RESULT_INFO_DICT,
    GET_RESULT_INFO_STR,
    POST_RESULT_EMBEDDING_STR,
    embedding_service_mock,  # noqa: F401
)
from wurzel.exceptions import (
    EmbeddingAPIException,
)
from wurzel.steps.embedding import (
    HuggingFaceInferenceAPIEmbeddings,
    PrefixedAPIEmbeddings,
)

GenericEmbedding = HuggingFaceInferenceAPIEmbeddings


FOR_EACH_EMBEDDING_CLASS = pytest.mark.parametrize(
    "EmbeddingClass,ConstKwargs",
    [
        (
            PrefixedAPIEmbeddings,
            {
                "url": "https://example.localhost.de",
                "prefix_mapping": {re.compile(r"."): ""},
            },
        ),
        (
            HuggingFaceInferenceAPIEmbeddings,
            {
                "url": "https://example.localhost.de",
            },
        ),
    ],
)


def validate_embedding(embedding):
    assert isinstance(embedding, list)
    assert len(embedding) > 1
    assert isinstance(embedding[0], float)


@FOR_EACH_EMBEDDING_CLASS
def init_test(EmbeddingClass: type[HuggingFaceInferenceAPIEmbeddings], ConstKwargs):
    _ = EmbeddingClass(**ConstKwargs)


@FOR_EACH_EMBEDDING_CLASS
def test_documents_for_each(
    EmbeddingClass: type[GenericEmbedding],
    ConstKwargs,
    embedding_service_mock,  # noqa: F811
):
    e = EmbeddingClass(**ConstKwargs)
    b = e.embed_documents(["aa", "bb"])
    assert len(b) == 2
    for emb in b:
        validate_embedding(emb)


@FOR_EACH_EMBEDDING_CLASS
def test_embedd_query_for_each(
    EmbeddingClass: type[GenericEmbedding],
    ConstKwargs,
    embedding_service_mock,  # noqa: F811
):
    e = EmbeddingClass(**ConstKwargs)
    a = e.embed_query("aa")
    validate_embedding(a)


@FOR_EACH_EMBEDDING_CLASS
def test_not_existent_embedding_service(EmbeddingClass: type[GenericEmbedding], ConstKwargs):
    class PrefixedAPIEmbeddingsMocked(EmbeddingClass):
        _timeout = 0.2

        def get_info(self):
            return GET_RESULT_INFO_DICT

    with pytest.raises(EmbeddingAPIException):
        embedding = PrefixedAPIEmbeddingsMocked(**ConstKwargs)
        embedding.embed_query("This has to be emebedded")


@FOR_EACH_EMBEDDING_CLASS
def test_invalid_embedding_contructor(EmbeddingClass: type[GenericEmbedding], ConstKwargs):
    with requests_mock.Mocker() as m:
        m.get("/info", text="invalid")
        m.post("/embed", text="invalid")
        with pytest.raises(EmbeddingAPIException):
            EmbeddingClass(**ConstKwargs)


@FOR_EACH_EMBEDDING_CLASS
def test_invalid_embedding_request(EmbeddingClass: type[GenericEmbedding], ConstKwargs):
    with requests_mock.Mocker() as m:
        m.get("/info", text=GET_RESULT_INFO_STR % "test")
        m.post("/embed", text=POST_RESULT_EMBEDDING_STR)
        em = EmbeddingClass(**ConstKwargs)
        m.get("/info", text='{"msg":"invalid"')
        m.post("/embed", text='{"msg":"invalid"')
        with pytest.raises(EmbeddingAPIException):
            em.embed_query("nope")


@FOR_EACH_EMBEDDING_CLASS
def test_service_status_code_failure(EmbeddingClass: type[GenericEmbedding], ConstKwargs):
    with requests_mock.Mocker() as m:
        m.get("/info", text=GET_RESULT_INFO_STR % "e5")
        m.post("/embed", text=POST_RESULT_EMBEDDING_STR, status_code=500)
        em = EmbeddingClass(**ConstKwargs)
        with pytest.raises(EmbeddingAPIException):
            em.embed_documents(["asd"])


@pytest.mark.parametrize("port", [None, 1234])
@pytest.mark.parametrize("scheme", ["http", "https"])
def test_url_schema(scheme: str, port):
    url_str = f"{scheme}://example.com.local"
    if port:
        url_str += f":{port}"
    url = Url(url_str)
    with requests_mock.Mocker() as m:
        m.get("/info", text=GET_RESULT_INFO_STR % "e5")
        m.post("/embed", text=POST_RESULT_EMBEDDING_STR, status_code=500)
        assert str(url) == f"{url_str}/"
        hgf = HuggingFaceInferenceAPIEmbeddings(str(url))
    assert hgf.info_url.port == port if port else {"http": 80, "https": 443}.get(scheme)
    assert str(hgf.info_url) == f"{url_str}/info"
