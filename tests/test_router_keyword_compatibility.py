from inspect import signature

from app.router import search_mine


def test_router_public_keyword_is_query():
    assert "query" in signature(search_mine).parameters


def test_non_lml_keyword_query():
    result = search_mine(
        query="99999-HQ-LML",
        top_k=5,
    )
    assert result["route"] == "licensing"


def test_lml_keyword_query():
    result = search_mine(
        query=(
            "What are the requirements for a "
            "large-scale mining licence in Zambia?"
        ),
        top_k=5,
    )

    assert result["route"] == "documents"
    assert result["results"]
