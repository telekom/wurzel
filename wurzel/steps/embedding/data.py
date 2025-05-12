# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

from pandera import Field
from pandera.typing import Series

from wurzel.datacontract import PanderaDataFrameModel


class EmbeddingResult(PanderaDataFrameModel):
    """data contract of embedding output."""

    text: Series[str]
    url: Series[str] = Field(nullable=True, default=" ", coerce=True, description="url used for search ")
    vector: Series[list[float]]
    keywords: Series[str] = Field(nullable=True, default=" ", coerce=True, description="Keywords used for search ")


class EmbeddingMultiVectorResult(PanderaDataFrameModel):
    """data contract of embedding output."""

    text: Series[str]
    url: Series[str] = Field(nullable=True, default=" ", coerce=True, description="url used for search ")
    vectors: Series[list[list[float]]]
    keywords: Series[str] = Field(nullable=True, default=" ", coerce=True, description="Keywords used for search ")
    splits: Series[list[str]] = Field(
        nullable=True,
        default=None,
        coerce=True,
        description="splits of the Multivector",
    )
