from app.project_estimates import extract_project_estimates


def test_amount_before_project_name():
    evidence = [{
        "source_id": "S1",
        "document": "usgs.html",
        "pages": "1",
        "text": (
            "Barrick Gold completed a feasibility study "
            "for a $2 billion expansion project at "
            "the Lumwana Mine to double copper output."
        ),
    }]

    result = extract_project_estimates("Lumwana", evidence)

    assert len(result) == 1
    assert result[0]["amount_usd"] == 2_000_000_000


def test_does_not_borrow_mopani_investment():
    evidence = [{
        "source_id": "S1",
        "document": "usgs.html",
        "pages": "1",
        "text": (
            "Barrick completed a feasibility study "
            "for a $2 billion expansion project at "
            "the Lumwana Mine. "
            "Mopani Copper Mines secured a "
            "\\$1.1 billion investment plan."
        ),
    }]

    result = extract_project_estimates("Lumwana", evidence)

    assert len(result) == 1
    assert result[0]["amount_usd"] == 2_000_000_000


def test_no_unrelated_backward_amount():
    evidence = [{
        "source_id": "S1",
        "document": "report.pdf",
        "pages": "1",
        "text": (
            "Another mine received $3 billion in funding. "
            "The Lumwana Mine was discussed separately."
        ),
    }]

    assert extract_project_estimates("Lumwana", evidence) == []


def test_same_source_does_not_duplicate_estimate():
    evidence = [{
        "source_id": "S1",
        "document": "report.pdf",
        "pages": "1",
        "text": (
            "Lumwana Mine received a $2 billion investment. "
            "A $2 billion expansion project at the Lumwana Mine "
            "was also described."
        ),
    }]

    result = extract_project_estimates("Lumwana", evidence)

    assert len(result) == 1
    assert result[0]["amount_usd"] == 2_000_000_000
