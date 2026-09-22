from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd
import streamlit as st


# =========================================================
# PROJECT PATH
# =========================================================

ROOT_DIR = Path(__file__).resolve().parents[2]

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(ROOT_DIR),
    )


# =========================================================
# MINELENS IMPORTS
# =========================================================

from app.search import load_chunks  # noqa: E402
from frontend.styles.theme import apply_theme  # noqa: E402
from frontend.utils.display import (  # noqa: E402
    clean_text,
    looks_like_filename,
    prettify_filename,
)


# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="Document Explorer | MineLens Zambia",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded",
)

apply_theme()


# =========================================================
# STATE
# =========================================================

FILTER_DEFAULTS = {
    "document_search": "",
    "document_agency_filter": [],
    "document_type_filter": [],
    "document_status_filter": [],
    "document_year_filter": [],
}


def reset_filters() -> None:
    """
    Clear all Document Explorer search filters.
    """

    for key, value in FILTER_DEFAULTS.items():

        if isinstance(value, list):
            st.session_state[key] = value.copy()

        else:
            st.session_state[key] = value


# =========================================================
# GENERIC HELPERS
# =========================================================

def text_value(
    item: dict,
    *keys: str,
) -> str:
    """
    Return the first non-empty text value from
    the supplied keys.
    """

    for key in keys:

        value = clean_text(
            item.get(key)
        )

        if value:
            return value

    return ""


def document_key(
    chunk: dict,
) -> str:
    """
    Build a stable key for grouping document chunks.
    """

    return (
        text_value(
            chunk,
            "source_id",
        )
        or text_value(
            chunk,
            "document",
        )
        or text_value(
            chunk,
            "source_title",
            "title",
        )
        or text_value(
            chunk,
            "chunk_id",
        )
    )


def document_title(
    chunk: dict,
) -> str:
    """
    Return a readable document title.
    """

    title = text_value(
        chunk,
        "source_title",
        "title",
    )

    if title:
        return title

    document = text_value(
        chunk,
        "document",
    )

    if document:

        name = Path(
            document
        ).name

        if looks_like_filename(
            name
        ):
            return prettify_filename(
                name
            )

        return name

    return "Untitled document"


def page_label(
    chunk: dict,
) -> str:
    """
    Return a readable page range.
    """

    page_start = chunk.get(
        "page_start"
    )

    page_end = chunk.get(
        "page_end"
    )

    if (
        page_start is None
        and page_end is None
    ):
        return ""

    if page_start is None:
        page_start = page_end

    if page_end is None:
        page_end = page_start

    if page_start == page_end:
        return str(
            page_start
        )

    return (
        f"{page_start}-{page_end}"
    )


def published_year(
    chunk: dict,
) -> str:
    """
    Extract a year from published_date.
    """

    published = text_value(
        chunk,
        "published_date",
    )

    if len(published) >= 4:
        candidate = published[:4]

        if candidate.isdigit():
            return candidate

    return ""


def source_url(
    chunk: dict,
) -> str:
    """
    Find an official source URL.
    """

    for key in (
        "source_url",
        "url",
        "source",
    ):

        value = clean_text(
            chunk.get(key)
        )

        if value.startswith(
            (
                "http://",
                "https://",
            )
        ):
            return value

    return ""


# =========================================================
# LOAD CORPUS
# =========================================================

@st.cache_data(
    show_spinner=False,
)
def load_document_chunks() -> list[dict]:
    """
    Load the current MineLens document corpus.
    """

    return load_chunks()


with st.spinner(
    "Loading MineLens document corpus..."
):

    chunks = load_document_chunks()


# =========================================================
# GROUP DOCUMENTS
# =========================================================

def group_documents(
    corpus: list[dict],
) -> list[dict]:
    """
    Convert chunk-level corpus data into
    document-level records.
    """

    grouped: dict[
        str,
        list[dict],
    ] = defaultdict(
        list
    )

    for chunk in corpus:

        key = document_key(
            chunk
        )

        if key:
            grouped[
                key
            ].append(
                chunk
            )

    documents: list[dict] = []

    for key, document_chunks in (
        grouped.items()
    ):

        first = document_chunks[0]

        pages: list[int] = []

        for chunk in document_chunks:

            for page_key in (
                "page_start",
                "page_end",
            ):

                value = chunk.get(
                    page_key
                )

                if isinstance(
                    value,
                    int,
                ):
                    pages.append(
                        value
                    )

        if pages:

            page_min = min(
                pages
            )

            page_max = max(
                pages
            )

            if page_min == page_max:
                pages_text = str(
                    page_min
                )

            else:
                pages_text = (
                    f"{page_min}-{page_max}"
                )

        else:
            pages_text = "—"

        documents.append(
            {
                "key": key,
                "title": document_title(
                    first
                ),
                "agency": text_value(
                    first,
                    "agency",
                ),
                "document_type": text_value(
                    first,
                    "document_type",
                ),
                "status": text_value(
                    first,
                    "source_status",
                    "status",
                ),
                "published_date": text_value(
                    first,
                    "published_date",
                ),
                "year": published_year(
                    first
                ),
                "document": text_value(
                    first,
                    "document",
                ),
                "source_url": source_url(
                    first
                ),
                "pages": pages_text,
                "chunk_count": len(
                    document_chunks
                ),
                "chunks": document_chunks,
            }
        )

    return sorted(
        documents,
        key=lambda item: (
            item["title"].casefold()
        ),
    )


documents = group_documents(
    chunks
)


# =========================================================
# FILTER HELPERS
# =========================================================

def unique_values(
    items: list[dict],
    key: str,
) -> list[str]:

    values = {
        clean_text(
            item.get(key)
        )
        for item in items
        if clean_text(
            item.get(key)
        )
    }

    return sorted(
        values,
        key=str.casefold,
    )


def matches_search(
    document: dict,
    query: str,
) -> bool:
    """
    Search document metadata and chunk text.
    """

    query = query.strip().casefold()

    if not query:
        return True

    metadata = " ".join(
        [
            clean_text(
                document.get(
                    "title"
                )
            ),
            clean_text(
                document.get(
                    "agency"
                )
            ),
            clean_text(
                document.get(
                    "document_type"
                )
            ),
            clean_text(
                document.get(
                    "document"
                )
            ),
        ]
    ).casefold()

    if query in metadata:
        return True

    for chunk in document[
        "chunks"
    ]:

        text = clean_text(
            chunk.get(
                "text"
            )
        ).casefold()

        if query in text:
            return True

    return False


def document_matches_filters(
    document: dict,
    *,
    search_query: str,
    agencies: list[str],
    document_types: list[str],
    statuses: list[str],
    years: list[str],
) -> bool:

    if not matches_search(
        document,
        search_query,
    ):
        return False

    if (
        agencies
        and document[
            "agency"
        ]
        not in agencies
    ):
        return False

    if (
        document_types
        and document[
            "document_type"
        ]
        not in document_types
    ):
        return False

    if (
        statuses
        and document[
            "status"
        ]
        not in statuses
    ):
        return False

    if (
        years
        and document[
            "year"
        ]
        not in years
    ):
        return False

    return True


# =========================================================
# MATCHING CHUNKS
# =========================================================

def matching_chunks_for_document(
    document: dict,
    query: str,
) -> list[dict]:
    """
    Return matching chunks for an active text search.

    With no text search, all chunks are returned.
    """

    query = query.strip().casefold()

    if not query:
        return document[
            "chunks"
        ]

    matching: list[dict] = []

    for chunk in document[
        "chunks"
    ]:

        text = clean_text(
            chunk.get(
                "text"
            )
        )

        metadata = " ".join(
            [
                document[
                    "title"
                ],
                document[
                    "agency"
                ],
                document[
                    "document_type"
                ],
                text,
            ]
        ).casefold()

        if query in metadata:

            matching.append(
                chunk
            )

    # If the document matched only through document-level
    # metadata, still provide its chunks for browsing.
    if not matching:
        return document[
            "chunks"
        ]

    return matching


def excerpt(
    chunk: dict,
    max_chars: int = 1200,
) -> str:
    """
    Return a readable document excerpt.
    """

    text = clean_text(
        chunk.get(
            "text"
        )
    )

    if not text:
        return (
            "No extracted text is available "
            "for this chunk."
        )

    if len(text) <= max_chars:
        return text

    return (
        text[
            :max_chars
        ].rstrip()
        + "..."
    )


# =========================================================
# HEADER
# =========================================================

st.markdown(
    """
    <div class="minelens-eyebrow">
        MineLens Zambia
    </div>

    <div class="minelens-title">
        Document Explorer
    </div>

    <div class="minelens-subtitle">
        Browse the official documents behind MineLens,
        including mining legislation, policy, strategy,
        licensing guidance, fees and statistical publications.
    </div>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# CORPUS METRICS
# =========================================================

agency_count = len(
    {
        document[
            "agency"
        ]
        for document in documents
        if document[
            "agency"
        ]
    }
)

document_type_count = len(
    {
        document[
            "document_type"
        ]
        for document in documents
        if document[
            "document_type"
        ]
    }
)


metric_1, metric_2, metric_3, metric_4 = (
    st.columns(
        4
    )
)


with metric_1:

    st.metric(
        "Documents",
        f"{len(documents):,}",
    )


with metric_2:

    st.metric(
        "Document chunks",
        f"{len(chunks):,}",
    )


with metric_3:

    st.metric(
        "Agencies",
        f"{agency_count:,}",
    )


with metric_4:

    st.metric(
        "Document types",
        f"{document_type_count:,}",
    )


st.divider()


# =========================================================
# SEARCH
# =========================================================

st.subheader(
    "Search documents"
)


search_column, clear_column = (
    st.columns(
        [5, 1]
    )
)


with search_column:

    search_query = st.text_input(
        "Search title, topic or document text",
        placeholder=(
            "e.g. critical minerals, "
            "application fee, geological data..."
        ),
        key="document_search",
    )


with clear_column:

    st.markdown(
        "<div style='height:28px;'></div>",
        unsafe_allow_html=True,
    )

    st.button(
        "Clear",
        use_container_width=True,
        on_click=reset_filters,
    )


# =========================================================
# FILTER OPTIONS
# =========================================================

agency_options = unique_values(
    documents,
    "agency",
)

document_type_options = unique_values(
    documents,
    "document_type",
)

status_options = unique_values(
    documents,
    "status",
)

year_options = sorted(
    unique_values(
        documents,
        "year",
    ),
    reverse=True,
)


# =========================================================
# FILTER CONTROLS
# =========================================================

filter_row_1 = st.columns(
    2
)


with filter_row_1[0]:

    selected_agencies = st.multiselect(
        "Agency",
        options=agency_options,
        key="document_agency_filter",
    )


with filter_row_1[1]:

    selected_types = st.multiselect(
        "Document type",
        options=document_type_options,
        key="document_type_filter",
    )


filter_row_2 = st.columns(
    2
)


with filter_row_2[0]:

    selected_statuses = st.multiselect(
        "Status",
        options=status_options,
        key="document_status_filter",
    )


with filter_row_2[1]:

    selected_years = st.multiselect(
        "Published year",
        options=year_options,
        key="document_year_filter",
    )


# =========================================================
# APPLY FILTERS
# =========================================================

filtered_documents = [
    document
    for document in documents
    if document_matches_filters(
        document,
        search_query=search_query,
        agencies=selected_agencies,
        document_types=selected_types,
        statuses=selected_statuses,
        years=selected_years,
    )
]


matching_chunk_count = sum(
    len(
        matching_chunks_for_document(
            document,
            search_query,
        )
    )
    for document in filtered_documents
)


# =========================================================
# RESULT METRICS
# =========================================================

st.divider()


result_metric_1, result_metric_2 = (
    st.columns(
        2
    )
)


with result_metric_1:

    st.metric(
        "Matching documents",
        f"{len(filtered_documents):,}",
    )


with result_metric_2:

    st.metric(
        "Matching chunks",
        f"{matching_chunk_count:,}",
    )


# =========================================================
# NO RESULTS
# =========================================================

if not filtered_documents:

    st.info(
        "No documents match the current "
        "search and filters."
    )

    st.stop()


# =========================================================
# DOCUMENT RESULTS TABLE
# =========================================================

st.subheader(
    "Documents"
)


document_rows: list[dict] = []


for document in filtered_documents:

    document_rows.append(
        {
            "Title": document[
                "title"
            ],
            "Agency": document[
                "agency"
            ],
            "Type": document[
                "document_type"
            ],
            "Status": document[
                "status"
            ],
            "Published": document[
                "published_date"
            ],
            "Pages": document[
                "pages"
            ],
            "Chunks": document[
                "chunk_count"
            ],
        }
    )


document_dataframe = pd.DataFrame(
    document_rows
)


table_event = st.dataframe(
    document_dataframe,
    use_container_width=True,
    hide_index=True,
    key="document_explorer_table",
    on_select="rerun",
    selection_mode="single-row",
    column_config={
        "Title":
            st.column_config.TextColumn(
                width="large",
            ),

        "Agency":
            st.column_config.TextColumn(
                width="medium",
            ),

        "Type":
            st.column_config.TextColumn(
                width="medium",
            ),

        "Status":
            st.column_config.TextColumn(
                width="small",
            ),

        "Published":
            st.column_config.TextColumn(
                width="medium",
            ),

        "Pages":
            st.column_config.TextColumn(
                width="small",
            ),

        "Chunks":
            st.column_config.NumberColumn(
                format="%d",
                width="small",
            ),
    },
)


# =========================================================
# SELECT DOCUMENT
# =========================================================

selected_rows = (
    table_event.selection.rows
)


if selected_rows:

    selected_index = (
        selected_rows[0]
    )

else:

    selected_index = 0


selected_document = (
    filtered_documents[
        selected_index
    ]
)


# =========================================================
# DOCUMENT DETAILS
# =========================================================

st.divider()

st.subheader(
    selected_document[
        "title"
    ]
)


detail_1, detail_2, detail_3, detail_4 = (
    st.columns(
        4
    )
)


with detail_1:

    st.metric(
        "Chunks",
        selected_document[
            "chunk_count"
        ],
    )


with detail_2:

    st.metric(
        "Pages",
        selected_document[
            "pages"
        ],
    )


with detail_3:

    st.metric(
        "Status",
        selected_document[
            "status"
        ]
        or "—",
    )


with detail_4:

    st.metric(
        "Published",
        selected_document[
            "published_date"
        ]
        or "—",
    )


if selected_document[
    "agency"
]:

    st.markdown(
        f"**Agency:** "
        f"{selected_document['agency']}"
    )


if selected_document[
    "document_type"
]:

    st.markdown(
        f"**Document type:** "
        f"{selected_document['document_type']}"
    )


if selected_document[
    "document"
]:

    st.caption(
        selected_document[
            "document"
        ]
    )


if selected_document[
    "source_url"
]:

    st.link_button(
        "Open official source",
        selected_document[
            "source_url"
        ],
    )


# =========================================================
# DOCUMENT EXCERPTS
# =========================================================

st.markdown(
    "### Document excerpts"
)


selected_chunks = (
    matching_chunks_for_document(
        selected_document,
        search_query,
    )
)


st.caption(
    f"Showing {len(selected_chunks):,} "
    f"relevant chunk"
    f"{'s' if len(selected_chunks) != 1 else ''} "
    f"from this document."
)


for index, chunk in enumerate(
    selected_chunks,
    start=1,
):

    pages = page_label(
        chunk
    )

    chunk_id = text_value(
        chunk,
        "chunk_id",
    )

    label = (
        f"{index}. "
        f"Pages {pages}"
        if pages
        else f"{index}. Document excerpt"
    )

    with st.expander(
        label,
        expanded=(
            index == 1
        ),
    ):

        st.markdown(
            excerpt(
                chunk
            )
        )

        if chunk_id:

            st.caption(
                f"Chunk: {chunk_id}"
            )