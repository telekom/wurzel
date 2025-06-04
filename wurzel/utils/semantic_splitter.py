# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

"""Semantic Markdown Splitter."""

import re
from logging import getLogger
from typing import TYPE_CHECKING, Optional, TypedDict

import mdformat
import tiktoken
from mistletoe import Document as MisDocument
from mistletoe import block_token, markdown_renderer, span_token
from mistletoe.token import Token

from wurzel.datacontract import MarkdownDataContract
from wurzel.exceptions import MarkdownException
from wurzel.utils.to_markdown.html2md import MD_RENDER_LOCK

if TYPE_CHECKING:
    import spacy
LEVEL_MAPPING = {
    block_token.Heading: 0,  # actually 1-6
    block_token.List: 7,
    block_token.CodeFence: 8,
    block_token.Table: 9,
    block_token.Paragraph: 10,
    block_token.ListItem: 11,
    block_token.TableRow: 12,
    span_token.LineBreak: 13,
    block_token.ThematicBreak: 14,
}
LEVEL_UNDEFINED = 15
OPENAI_ENCODING = tiktoken.encoding_for_model("gpt-3.5-turbo")

log = getLogger(__name__)


class MetaDataDict(TypedDict):
    """Dict definition of metadata."""

    keywords: str
    url: str


class DocumentNode(TypedDict):
    """Dict definition of internal tree structure for splitting."""

    highest_level: int
    token_len: int
    text: str
    children: list["DocumentNode"]
    metadata: MetaDataDict


def _get_token_len(text: str) -> int:
    """Get OpenAI Token length.

    Args:
        text (str): Test to encode

    Returns:
        int: count of tokens

    """
    return len(OPENAI_ENCODING.encode(text))


def _is_all_children_same_level(children: list[DocumentNode]) -> bool:
    nbr_different_level = len({c["highest_level"] for c in children})
    return nbr_different_level == 1


def _get_children_sorted_by_level(
    children: list[DocumentNode],
) -> list[tuple[int, int]]:
    return sorted(
        [(i, c["highest_level"]) for i, c in enumerate(children)],
        key=lambda x: x[1],
        reverse=False,
    )


def _get_highest_index_of_children(children: list[DocumentNode]) -> int:
    sorted_by_level = _get_children_sorted_by_level(children)
    return sorted_by_level[0][0]


def _get_highest_level_of_children(children: list[DocumentNode]) -> int:
    sorted_by_level = _get_children_sorted_by_level(children)
    return sorted_by_level[0][1]


def _get_heading_text(token: block_token.Heading):
    """Get heading text from Mistletoe heading block token."""
    if token.content:
        return token.content
    if "children" in vars(token) and len(token.children) > 0:
        return " ".join([c.content for c in token.children if hasattr(c, "content")])
    return ""


def _is_standalone_a_heading(text):
    childs = MisDocument(text).children
    if len(childs) != 1:
        return False
    return isinstance(childs[0], block_token.Heading)


def _cut_to_tokenlen(text: str, token_len: int) -> str:
    """Cut Text to token length using OpenAI."""
    tokens_old = OPENAI_ENCODING.encode(text)
    if len(tokens_old) > token_len:
        tokens = tokens_old[:token_len]
        return OPENAI_ENCODING.decode(tokens)
    return OPENAI_ENCODING.decode(tokens_old)


def _format_markdown_docs(
    docs: list[MarkdownDataContract],
) -> list[MarkdownDataContract]:
    """Formats the Markdown Document by the standards."""
    return [
        MarkdownDataContract(
            md=mdformat.text(doc.md).strip(),
            url=doc.url,
            keywords=doc.keywords,
        )
        for doc in docs
    ]


class WurzelMarkdownRenderer(markdown_renderer.MarkdownRenderer):
    """Fix For markdown_renderer.MarkdownRenderer."""

    # pylint: disable=unused-argument, arguments-differ
    def render_table_cell(self, token: block_token.TableCell, max_line_length: int) -> str:
        """Renders the content of a table cell.

        Args:
            token (block_token.TableCell): The table cell token to render.
            max_line_length (int): The maximum allowed line length for the content.

        Returns:
            str: The rendered content of the table cell.

        """
        return self.render_inner(token)

    def render_table_row(self, token: block_token.TableRow, max_line_length: int) -> str:
        """Renders a table row from the given token.

        Args:
            token (block_token.TableRow): The table row token to be rendered.
            max_line_length (int): The maximum allowed line length for the rendered row.

        Returns:
            str: The rendered table row as a string.

        """
        return self.render_inner(token)


class SemanticSplitter:
    """Splitter implementation."""

    nlp: "spacy.language.Language"
    token_limit: int
    token_limit_buffer: int
    token_limit_min: int

    def __init__(
        self,
        token_limit: int = 256,
        token_limit_buffer: int = 32,
        token_limit_min: int = 64,
        spacy_model: str = "de_core_news_sm",
    ) -> None:
        """Initializes the SemanticSplitter class with specified token limits and a spaCy language model.

        Args:
            token_limit (int, optional): The maximum number of tokens allowed. Defaults to 256.
            token_limit_buffer (int, optional): The buffer size for token limit to allow flexibility. Defaults to 32.
            token_limit_min (int, optional): The minimum number of tokens required. Defaults to 64.
            spacy_model (str, optional): The name of the spaCy language model to load. Defaults to "de_core_news_sm".

        Raises:
            OSError: If the specified spaCy model cannot be loaded.

        """
        import spacy  # pylint: disable=import-outside-toplevel

        self.nlp = spacy.load(spacy_model)
        self.token_limit = token_limit
        self.token_limit_buffer = token_limit_buffer
        self.token_limit_min = token_limit_min

    def _is_short(self, text: str) -> bool:
        return _get_token_len(text) <= self.token_limit - self.token_limit_buffer

    def _is_table(self, doc: DocumentNode) -> bool:
        return doc["highest_level"] == LEVEL_MAPPING[block_token.Table]

    def _is_within_targetlen_w_buffer(self, text: str) -> bool:
        length = _get_token_len(text)
        return self.token_limit + self.token_limit_buffer >= length >= self.token_limit - self.token_limit_buffer

    def _render_doc(self, doc: MisDocument) -> str:
        """Render Mistletoe Markdown Document."""
        try:
            with MD_RENDER_LOCK, WurzelMarkdownRenderer() as renderer:
                return renderer.render(doc)  # type: ignore[no-any-return]
        except Exception as e:
            raise MarkdownException(e) from e

    def _get_custom_level(self, block: block_token.BlockToken) -> int:
        """Get the hierarchical level for a mistletoe node."""
        if isinstance(block, block_token.Heading):
            return int(block.level)
        return LEVEL_MAPPING.get(type(block), LEVEL_UNDEFINED)

    def _merge_children(self, children: list[DocumentNode]) -> MisDocument:
        """Create a document out of a list of children."""
        new_doc = MisDocument([])
        # If all children a span tokens add them to a paragraph
        # because problems otherwise
        if all(isinstance(c, span_token.SpanToken) for c in children):
            para = block_token.Paragraph([])
            para.children = children
            new_doc.children += [para]
        else:
            new_doc.children += children
        return new_doc

    def _find_highest_level(self, children: list[DocumentNode], min_level: int = 0) -> tuple[int, Optional[Token], Optional[DocumentNode]]:
        """Among a list of children nodes find the one with the highest level.

        Return a tuple of that level, level node type and that child.
        """

        def is_any_children(children: list[DocumentNode], block_type: type[block_token.BlockToken]):
            """Check if any Mistletoe Node (child) is of specific type."""
            for child in children:
                if isinstance(child, block_type):
                    return True
            return False

        highest_level: int = LEVEL_UNDEFINED
        highest_type: Optional[type[Token]] = None
        highest_element: Optional[DocumentNode] = None

        if children is None:
            return (LEVEL_UNDEFINED, None, None)
        # Checked by higher level function
        for child in children:
            if isinstance(child, block_token.Heading) and child.level > min_level:
                if child.level < highest_level:
                    highest_level = int(child.level)
                    highest_type = block_token.Heading
                    highest_element = child

        # block_token.ThematicBreak
        # If level is not set by the Heading
        for block_type in [
            block_token.List,
            block_token.CodeFence,
            block_token.Table,
            block_token.Paragraph,
            block_token.ListItem,
            block_token.TableRow,
            span_token.LineBreak,  # Add table
            block_token.ThematicBreak,
        ]:
            if (highest_level == LEVEL_UNDEFINED) and is_any_children(children, block_type) and (LEVEL_MAPPING[block_type] > min_level):
                highest_level = LEVEL_MAPPING[block_type]
                highest_type = block_type
                highest_element = [child for child in children if isinstance(child, block_type)][0]
                break

        return highest_level, highest_type, highest_element

    def _split_children(self, children: list[MisDocument], min_level: int = 0) -> list[MisDocument]:
        """Split a list of children in the most semantic way and return a list of Documents with them merged."""
        if len(children) == 1:
            if "children" in vars(children[0]) or "_children" in vars(children[0]):
                return self._split_children(children[0].children)
            return [children[0]]
        highest_level, highest_type, _ = self._find_highest_level(children, min_level)

        # No higher splitter found
        if highest_level == LEVEL_UNDEFINED:
            return children
        assert highest_type
        # Find point to split the list of children
        split_points: list[int] = []
        for i, child in enumerate(children):
            if isinstance(child, highest_type):
                if highest_level == self._get_custom_level(child):
                    split_points.append(i)

        # There must be at least one split if highest_level < LEVEL_UNDEFINED
        # Highest splitter is first element
        if (split_points[0] == 0) and len(split_points) == 1:
            # Remove leading line breaks
            if isinstance(children[0], span_token.LineBreak):
                children = children[1:]
            # run again with lower level requirement
            return self._split_children(children, highest_level)

        # Combine Children to Documents
        prev_i = 0
        return_docs = []
        for i in split_points:
            if children[prev_i:i]:
                new_doc = self._merge_children(children[prev_i:i])
                return_docs.append(new_doc)
            prev_i = i
        new_doc = self._merge_children(children[split_points[-1] :])
        return_docs.append(new_doc)
        return return_docs

    def text_sentences(self, text):
        """Split a text into sentences using a NLP model.

        This does not use a Regex based approach on purpose as they break with
        punctuation very easily see: https://stackoverflow.com/a/61254146
        """
        return [sentence_span.text for sentence_span in self.nlp(text).sents]

    def _markdown_hierarchy_parser(self, text: str, metadata: MetaDataDict, max_depth: int = 30) -> DocumentNode:
        """Splits a Markdown string into a semantic Markdown based hierarchy.

        Given a Markdown string it hierarchically splits that text using
        the semantic information from the Markdown document until
        all final leaf nodes are below the global token limit.

        max_depth decreases with every recursive call of the function
        controlling the maximum depth of the hierarchy.
        """
        md_doc = MisDocument(text)
        highest_level, _, _ = self._find_highest_level(md_doc.children)
        token_len = _get_token_len(text)

        # Reached max recursion depth
        if max_depth == 0:
            log.warning("maximal markdown recursion reached")
            return DocumentNode(
                highest_level=highest_level,
                token_len=token_len,
                text=text,
                metadata=metadata,
                children=[],
            )

        # Do further hierarchy parsing
        splits: MisDocument = self._split_children(md_doc.children)

        def has_node_a_known_level(x):
            return any(isinstance(x.children[0] if isinstance(x, MisDocument) else x, cl) for cl in LEVEL_MAPPING)

        no_child_has_a_known_level = not any(has_node_a_known_level(x) for x in splits)
        # No child has a known level this means we only have sentences and no more semantic information
        if no_child_has_a_known_level:
            return DocumentNode(
                highest_level=highest_level,
                token_len=token_len,
                text=text,
                metadata=metadata,
                children=[
                    DocumentNode(
                        highest_level=highest_level,
                        token_len=_get_token_len(sent),
                        text=sent,
                        metadata=metadata,
                        children=[],
                    )
                    for sent in self.text_sentences(text)
                ],
            )

        # Further split the child nodes until we reach the token limit for each
        children: list[DocumentNode] = []
        for s in splits:
            if not hasattr(s, "children"):
                continue
            md_child = self._render_doc(s)
            highest_level_child, _, _ = self._find_highest_level(s.children)
            children.append(
                DocumentNode(
                    highest_level=highest_level_child,
                    text=md_child,
                    token_len=_get_token_len(md_child),
                    children=[self._markdown_hierarchy_parser(md_child, metadata, max_depth - 1)],
                    metadata=metadata,
                )
            )
        return DocumentNode(
            highest_level=highest_level,
            token_len=token_len,
            text=text,
            children=children,
            metadata=metadata,
        )

    # unused
    def _split_by_sentence(self, text: str) -> list[str]:
        """Sometimes _split_children does not find children leafs with are smaller then TOKEN_LIMIT.

        Thus we need to split by sentence.
        """
        token_limit = self.token_limit
        token_buffer = self.token_limit_buffer
        lenth = _get_token_len(text)
        needed_splits = lenth // token_limit
        if not needed_splits:
            return [text]
        sentences = [(_get_token_len(sent), f"{sent}. ") for sent in re.split(r"\.(?=\s|\\n)", text) if sent.strip()]
        chunks: list[str] = []
        chunk = ""
        chunk_len = 0
        for size, sent in sentences:
            if size > token_limit + token_buffer:  # single big sentence
                if chunk:  # then add last
                    chunks.append(chunk)
                    chunk = ""
                    chunk_len = 0
                chunks.append(_cut_to_tokenlen(sent, token_limit))  # cut this
                # Last piece of sentence is discarded
                continue
            if chunk_len + size > token_limit + token_buffer:  # with next to big
                chunks.append(chunk)
                chunk = ""
                chunk_len = 0
            chunk += sent
            chunk_len += size
            if token_limit + token_buffer >= chunk_len >= token_limit - token_buffer:  # together they fit
                chunks.append(chunk)

                chunk = ""
                chunk_len = 0
        if chunk:
            chunks.append(_cut_to_tokenlen(chunk, token_limit))
        # chunks = [
        #    (chunk.replace("\n").strip() if not "#" else chunk.strip()) for chunk in chunks
        # ] This was broken
        chunks = [
            (_cut_to_tokenlen(chunk, token_limit) if not self._is_within_targetlen_w_buffer(chunk) or self._is_short(chunk) else chunk)
            for chunk in chunks
        ]
        for chunk in chunks:
            assert self._is_within_targetlen_w_buffer(chunk) or self._is_short(chunk)
        return chunks

    # pylint: disable-next=too-many-positional-arguments
    def _handle_parsing_of_children(
        self,
        doc: DocumentNode,
        child: DocumentNode,
        text_w_prev_child: str,
        remaining_snipped: str,
        recursive_depth: int,
    ) -> tuple[str, list[MarkdownDataContract]]:
        """Handle the parsing of child nodes during hierarchical parsing.

        This method is used to process child nodes of a document node and determine
        how their text content should be handled based on specific conditions. It
        helps manage recursion depth and ensures the text is split into manageable
        Markdown data contracts.

            doc (DocumentNode): The parent document node containing metadata and text.
            child (DocumentNode): The child document node to be processed.
            text_w_prev_child (str): The text content combined with the previous child node.
            remaining_snipped (str): The remaining text snippet to be processed.
            recursive_depth (int): Tracks the current recursion depth during hierarchical parsing.

            tuple[str, list[MarkdownDataContract]]:
                - A string representing the remaining unprocessed text snippet.
                - A list of MarkdownDataContract objects containing processed Markdown data.

        """
        return_doc = []
        if self._is_short(text_w_prev_child):
            remaining_snipped = text_w_prev_child
        elif self._is_within_targetlen_w_buffer(text_w_prev_child):
            child["text"] = text_w_prev_child
            return_doc += [
                MarkdownDataContract(
                    md=_cut_to_tokenlen(child["text"], self.token_limit),
                    url=child["metadata"]["url"],
                    keywords=child["metadata"]["keywords"],
                )
            ]
            remaining_snipped = ""
        else:
            if not _is_standalone_a_heading(remaining_snipped):
                if _get_token_len(remaining_snipped) >= self.token_limit_min:
                    return_doc.append(
                        MarkdownDataContract(
                            md=remaining_snipped,
                            keywords=doc["metadata"]["keywords"],
                            url=doc["metadata"]["url"],
                        )
                    )
                remaining_snipped = ""
                if self._is_within_targetlen_w_buffer(child["text"]):
                    return_doc.append(self._md_data_from_dict_cut(child))
                else:
                    return_doc += self._parse_hierarchical(child, recursive_depth + 1)
            else:
                temp_docs = self._parse_hierarchical(child, recursive_depth + 1)
                return_doc += [
                    MarkdownDataContract(
                        md=remaining_snipped + "\n\n" + d.md,
                        keywords=d.keywords,
                        url=d.url,
                    )
                    for d in temp_docs
                ]
        return remaining_snipped, return_doc

    def _md_data_from_dict_cut(self, doc):
        return MarkdownDataContract(
            md=_cut_to_tokenlen(doc["text"], self.token_limit),
            url=doc["metadata"]["url"],
            keywords=doc["metadata"]["keywords"],
        )

    def _parse_hierarchical(
        self,
        doc: DocumentNode,
        recursive_depth: int = 1,
    ) -> list[MarkdownDataContract]:
        if _get_token_len(doc["text"]) <= self.token_limit_min:
            if recursive_depth == 1:
                return [self._md_data_from_dict_cut(doc)]
            log.warning("document to short", extra=doc)
            return []
        if self._is_within_targetlen_w_buffer(doc["text"]):
            return [self._md_data_from_dict_cut(doc)]
        if "children" not in doc.keys():
            log.warning(
                "no remaining children. still to big -> sentence split by dot",
                extra=doc,
            )
            return [self._md_data_from_dict_cut(doc)]
        if self._is_table(doc):
            log.warning(
                "found table, that should have been split, cutting off",
                extra=doc["metadata"],
            )
            return [self._md_data_from_dict_cut(doc)]
        if len(doc["children"]) == 0:
            log.warning(
                "no remaining children. still to big -> Cut by tokenlen",
                extra=doc,
            )
            return [self._md_data_from_dict_cut(doc)]
        if len(doc["children"]) == 1:
            return self._parse_hierarchical(doc["children"][0])

        children = doc["children"]
        return_doc: list[MarkdownDataContract] = []

        # If we don't have a proper hierarchy, handle the elements before top item separately
        if not _is_all_children_same_level(children):
            idx_highest = _get_highest_index_of_children(children)
            highest_child_is_heading = _get_highest_level_of_children(children) <= 6
            first_child_is_highest = idx_highest == 0
            if not first_child_is_highest and highest_child_is_heading:
                text_until_highest_child = "\n".join([c["text"] for c in children[:idx_highest]])
                token_len = _get_token_len(text_until_highest_child)
                max_level = max(c["highest_level"] for c in children[:idx_highest])
                new_doc = DocumentNode(
                    highest_level=max_level,
                    token_len=token_len,
                    text=text_until_highest_child,
                    children=children[:idx_highest],
                    metadata=doc["metadata"],
                )
                return_doc += self._parse_hierarchical(new_doc)
                children = children[idx_highest:]

        remaining_snipped = ""
        for child in children:
            child["metadata"] = doc["metadata"]  # inherit metadata downwards
            text_w_prev_child = "\n".join([remaining_snipped, child["text"]]).strip()
            remaining_snipped, returned_docs = self._handle_parsing_of_children(
                doc, child, text_w_prev_child, remaining_snipped, recursive_depth
            )
            return_doc += returned_docs

        # add potential short remaining spillovers
        if _get_token_len(remaining_snipped) >= self.token_limit_min:
            return_doc += [
                MarkdownDataContract(
                    md=_cut_to_tokenlen(remaining_snipped, self.token_limit),
                    url=doc["metadata"]["url"],
                    keywords=doc["metadata"]["keywords"],
                )
            ]
        return return_doc

    def _adopt_splitted_list_to_use_highest_prev_header(
        self,
        docs: list[MarkdownDataContract],
    ) -> list[MarkdownDataContract]:
        """Function to improve the semantic meaning of the Markdown document by reattaching a parent heading.

        Does not yet respect the token limit, however headings usually have little impact
        """
        highest_header_until_now = {i + 1: "" for i in range(6)}
        for doc in docs:
            text = doc.md.strip()
            md_doc = MisDocument(text)
            # Create Header
            highest_level, highest_type, highest_child = self._find_highest_level(md_doc.children)
            if str(highest_type) == str(block_token.Heading):
                # Discuss this
                # highest_header_until_now[highest_level] = _get_heading_text(highest_child)
                highest_header_until_now[highest_level] = self._render_doc(highest_child).lstrip(" #")

            ordered_headers = {level: text for level, text in highest_header_until_now.items() if text}
            docwide_highest_level = min(ordered_headers.keys()) if ordered_headers else 10
            new_header = " - ".join([text for level, text in ordered_headers.items() if level < highest_level])
            if new_header:
                new_header = "# " + new_header
            # Filter Doc
            document_is_just_single_header = text.strip().startswith("#") and "\n" not in text.strip()
            if document_is_just_single_header:
                continue
            # TODOo check token limit or limit header lenght
            # The higher heading the lower its level
            doc_has_lower_heading = docwide_highest_level < highest_level
            new_doc = text.strip() if not doc_has_lower_heading else (new_header + "\n\n" + doc.md).strip()
            doc.md = new_doc

        return docs

    def split_markdown_document(self, doc: MarkdownDataContract) -> list[MarkdownDataContract]:
        """Split a Markdown Document into Snippets."""
        metadata = MetaDataDict(url=doc.url, keywords=doc.keywords)
        doc_hierarchy: DocumentNode = self._markdown_hierarchy_parser(doc.md, metadata)
        doc_snippets: list[MarkdownDataContract] = self._parse_hierarchical(doc_hierarchy)
        improved_snippets: list[MarkdownDataContract] = self._adopt_splitted_list_to_use_highest_prev_header(doc_snippets)
        formatted_snippets: list[MarkdownDataContract] = _format_markdown_docs(improved_snippets)
        return formatted_snippets
