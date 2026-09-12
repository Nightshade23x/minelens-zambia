from __future__ import annotations

import pytest

from app.router import (
    ROUTE_DOCUMENTS,
    ROUTE_LICENSING,
    route_query,
)


# ---------------------------------------------------------
# Structured licensing routing
# ---------------------------------------------------------

def test_exact_licence_code_routes_to_licensing() -> None:

    result = route_query(
        "42553-HQ-LML"
    )

    assert (
        result[
            "route"
        ]
        == ROUTE_LICENSING
    )


def test_decision_query_routes_to_licensing() -> None:

    result = route_query(
        "which exploration licences "
        "were rejected"
    )

    assert (
        result[
            "route"
        ]
        == ROUTE_LICENSING
    )


def test_company_listing_routes_to_licensing() -> None:

    result = route_query(
        "which companies received "
        "mining licences"
    )

    assert (
        result[
            "route"
        ]
        == ROUTE_LICENSING
    )


def test_location_filtered_licences_route_to_licensing() -> None:

    result = route_query(
        "copper licences in Solwezi"
    )

    assert (
        result[
            "route"
        ]
        == ROUTE_LICENSING
    )


# ---------------------------------------------------------
# Document routing
# ---------------------------------------------------------

def test_cost_query_routes_to_documents() -> None:

    result = route_query(
        "how much does a large scale "
        "mining licence cost"
    )

    assert (
        result[
            "route"
        ]
        == ROUTE_DOCUMENTS
    )


def test_fee_query_routes_to_documents() -> None:

    result = route_query(
        "large scale mining licence fee"
    )

    assert (
        result[
            "route"
        ]
        == ROUTE_DOCUMENTS
    )


def test_requirements_query_routes_to_documents() -> None:

    result = route_query(
        "what documents are required "
        "for a mining licence"
    )

    assert (
        result[
            "route"
        ]
        == ROUTE_DOCUMENTS
    )


def test_critical_minerals_routes_to_documents() -> None:

    result = route_query(
        "what are Zambia's critical minerals"
    )

    assert (
        result[
            "route"
        ]
        == ROUTE_DOCUMENTS
    )


def test_employment_query_routes_to_documents() -> None:

    result = route_query(
        "how many people work in mines"
    )

    assert (
        result[
            "route"
        ]
        == ROUTE_DOCUMENTS
    )


def test_generic_mining_licences_defaults_to_documents() -> None:

    result = route_query(
        "mining licences"
    )

    assert (
        result[
            "route"
        ]
        == ROUTE_DOCUMENTS
    )


def test_document_intent_overrides_decision_word() -> None:

    result = route_query(
        "what is the fee for an approved "
        "large scale mining licence"
    )

    assert (
        result[
            "route"
        ]
        == ROUTE_DOCUMENTS
    )


# ---------------------------------------------------------
# Validation
# ---------------------------------------------------------

def test_empty_query_is_rejected() -> None:

    with pytest.raises(
        ValueError
    ):

        route_query(
            "   "
        )