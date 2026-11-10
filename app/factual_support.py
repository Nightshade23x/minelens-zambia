"""Conservative factual checks for selected MineLens answers."""

import re


PRODUCTION_RE = re.compile(
    r"(?<![\w.,])(?P<amount>\d[\d,]*(?:\.\d+)?)\s*"
    r"(?P<unit>metric\s+(?:tonnes?|tons?)|"
    r"tonnes?|tons?|kilograms?|kg|t)\b",
    re.I,
)

MONEY_RE = re.compile(
    r"(?P<op>>=|<=|>|<|≥|≤|~|≈)?\s*\$\s*"
    r"(?P<number>\d+(?:\.\d+)?)\s*"
    r"(?P<unit>billions?|bn|b|millions?|mn|m)\b",
    re.I,
)

CITE_RE = re.compile(r"\[(S[1-9]\d*)\]")


def _words(value):
    return re.findall(
        r"[a-z0-9]+",
        str(value or "").casefold(),
    )


def _money_value(match, prefix=""):
    unit = match.group("unit").casefold()

    scale = (
        1_000_000_000
        if unit.startswith("b")
        else 1_000_000
    )

    amount = float(match.group("number")) * scale

    operator = match.group("op") or "="

    operator = {
        "≥": ">=",
        "≤": "<=",
        "~": "~",
        "≈": "~",
    }.get(operator, operator)

    if operator == "=":
        if re.search(
            r"(?:greater|more)\s+than\s*$|"
            r"(?:over|above)\s*$",
            prefix,
            re.I,
        ):
            operator = ">"

        elif re.search(
            r"at\s+least\s*$",
            prefix,
            re.I,
        ):
            operator = ">="

    return operator, amount


def _mingomba_estimate(text):
    """Find the first monetary estimate after a Mingomba mention."""

    for occurrence in re.finditer(
        r"\bmingomba\b",
        text,
        re.I,
    ):
        nearby = text[
            occurrence.end():occurrence.end() + 160
        ]

        match = MONEY_RE.search(nearby)

        if match:
            prefix = nearby[
                max(0, match.start() - 40):match.start()
            ]

            return _money_value(match, prefix)

    return None


def validate_factual_support(
    question: str,
    search_result: dict,
    answer_result: dict,
    evidence=None,
) -> dict:
    """
    Verify supported claim types.

    checked=False means the answer was not verified.
    It does not mean the answer is correct.
    """

    route = search_result.get("route")
    answer = str(answer_result.get("answer") or "")
    records = search_result.get("results") or []

    checks = []
    issues = []

    if not records:
        return {
            "checked": False,
            "supported": None,
            "checks": [],
            "issues": [],
            "reason": "No records; abstention checked separately.",
        }

    # --------------------------------------------------
    # Facility operator
    # --------------------------------------------------

    if (
        route == "facilities"
        and re.search(
            r"\b(?:operat(?:e|es|or)|who\s+runs)\b",
            question,
            re.I,
        )
    ):
        matched = []

        for item in records:
            facility = item.get("facility", {})
            name = str(facility.get("facility_name") or "")

            if name and re.search(
                r"(?<!\w)" + re.escape(name) + r"(?!\w)",
                question,
                re.I,
            ):
                matched.append(facility)

        if not matched:
            return {
                "checked": False,
                "supported": None,
                "checks": [],
                "issues": [],
                "reason": "No exact named facility matched.",
            }

        operators = [
            str(operator)
            for facility in matched
            for operator in facility.get(
                "major_operating_companies", []
            )
            if operator
        ]

        claimed = re.search(
            r"\b(?:operated\s+by|operator\s+is)\s+"
            r"(.+?)(?=\s*\[S\d+\]|[.!?](?:\s|$)|$)",
            answer,
            re.I | re.S,
        )

        if claimed:
            valid = any(
                _words(claimed.group(1)) == _words(operator)
                for operator in operators
            )
        else:
            valid = any(
                re.search(
                    r"(?<!\w)" + re.escape(operator) + r"(?!\w)",
                    answer,
                    re.I,
                )
                for operator in operators
            )

        checks.append("facility_operator")

        if not valid:
            issues.append(
                "The claimed operator does not match "
                "the retrieved facility's operator field."
            )

    # --------------------------------------------------
    # Country mineral production
    # --------------------------------------------------


    elif (
        route == "mining_statistics"
        and re.search(
            r"\b(?:produc(?:e|ed|tion)|output)\b",
            question,
            re.I,
        )
    ):
        relevant = sorted(
            [
                record
                for record in records
                if record.get("production") is not None
                and record.get("year") is not None
            ],
            key=lambda record: int(record["year"]),
        )

        if relevant:
            checks.append(
                "production_value_country_commodity_year"
            )

            quantities = list(PRODUCTION_RE.finditer(answer))

            requested_years = {
                int(year)
                for year in re.findall(
                    r"\b(?:19|20)\d{2}\b", question
                )
            }

            is_trend = (
                search_result.get("statistics_intent") == "trend"
                or bool(re.search(
                    r"\b(?:trend|change|increased|decreased)\b",
                    question,
                    re.I,
                ))
            )

            def unit_matches(claim_unit, record):
                source_unit = str(
                    record.get("unit") or ""
                ).casefold().strip()

                if not source_unit:
                    return True

                claim_kg = claim_unit.casefold().startswith(
                    ("kg", "kilogram")
                )

                if "kg" in source_unit or "kilogram" in source_unit:
                    return claim_kg

                metric = (
                    "metr" in source_unit
                    or "tonne" in source_unit
                    or "ton" in source_unit
                    or source_unit == "t"
                )

                return metric and not claim_kg

            if not quantities:
                issues.append(
                    "No recognized production quantity found."
                )

            for match in quantities:
                amount = float(
                    match.group("amount").replace(",", "")
                )

                unit = match.group("unit")

                tail = answer[
                    match.end():match.end() + 80
                ]

                tail = re.split(
                    r"[.!?](?:\*{0,2})\s+",
                    tail,
                    maxsplit=1,
                )[0]

                nearby_year = re.search(
                    r"(?:\bin\s*|(?<![a-z0-9]))"
                    r"((?:19|20)\d{2})\b",
                    tail,
                    re.I,
                )

                if nearby_year:
                    year = int(nearby_year.group(1))

                    supported = any(
                        abs(
                            amount - float(record["production"])
                        ) <= 0.001
                        and int(record["year"]) == year
                        and unit_matches(unit, record)
                        and (
                            not requested_years
                            or year in requested_years
                        )
                        for record in relevant
                    )

                else:
                    prefix = answer[
                        max(0, match.start() - 80):
                        match.start()
                    ]

                    is_change = (
                        is_trend
                        and bool(re.search(
                            r"(?:overall\s+)?change\s+was"
                            r"|(?:increased|decreased)\s+by"
                            r"|(?:increase|decrease)\s+of",
                            prefix,
                            re.I,
                        ))
                    )

                    if is_change and len(relevant) >= 2:
                        first = relevant[0]
                        last = relevant[-1]

                        difference = abs(
                            float(last["production"])
                            - float(first["production"])
                        )

                        supported = (
                            abs(amount - difference) <= 0.001
                            and unit_matches(unit, first)
                            and unit_matches(unit, last)
                        )

                    else:
                        supported = any(
                            abs(
                                amount - float(record["production"])
                            ) <= 0.001
                            and unit_matches(unit, record)
                            and (
                                not requested_years
                                or int(record["year"])
                                in requested_years
                            )
                            for record in relevant
                        )

                if not supported:
                    issues.append(
                        "Unsupported production quantity: "
                        + match.group(0)
                    )

            if is_trend and len(relevant) >= 2:
                percentages = re.findall(
                    r"(?<![\w.,])(\d+(?:\.\d+)?)\s*%",
                    answer,
                )

                first_value = float(
                    relevant[0]["production"]
                )

                if percentages and first_value != 0:
                    last_value = float(
                        relevant[-1]["production"]
                    )

                    expected_percent = abs(
                        (last_value - first_value)
                        / first_value * 100
                    )

                    checks.append(
                        "production_trend_percentage"
                    )

                    for percentage in percentages:
                        if abs(
                            float(percentage) - expected_percent
                        ) > 0.02:
                            issues.append(
                                "Unsupported trend percentage: "
                                + percentage + "%"
                            )

            known_entities = any(
                str(record.get("country") or "").casefold()
                in answer.casefold()
                and str(record.get("commodity") or "").casefold()
                in answer.casefold()
                for record in relevant
                if record.get("country")
                and record.get("commodity")
            )

            if not known_entities:
                issues.append(
                    "Country or commodity does not match "
                    "the production records."
                )

    # --------------------------------------------------
    # Mingomba capital expenditure
    # --------------------------------------------------

    elif (
        route == "documents"
        and re.search(r"\bmingomba\b", question, re.I)
        and re.search(
            r"\b(?:capex|capital expenditure)\b",
            question,
            re.I,
        )
    ):
        evidence_by_id = {
            str(item.get("source_id")):
                str(item.get("text") or "")
            for item in (evidence or [])
            if isinstance(item, dict)
        }

        money_matches = list(
            MONEY_RE.finditer(answer)
        )

        for index, match in enumerate(money_matches):
            next_start = (
                money_matches[index + 1].start()
                if index + 1 < len(money_matches)
                else len(answer)
            )

            following_text = answer[
                match.end():
                min(next_start, match.end() + 100)
            ]

            citation = CITE_RE.search(following_text)

            if not citation:
                checks.append("mingomba_capex:missing_citation")
                issues.append(
                    "A Mingomba CapEx amount has no nearby citation."
                )
                continue

            source_id = citation.group(1)

            prefix = answer[
                max(0, match.start() - 45):
                match.start()
            ]

            claim = _money_value(match, prefix)

            supporting_value = _mingomba_estimate(
                evidence_by_id.get(source_id, "")
            )

            checks.append(
                f"mingomba_capex:{source_id}"
            )

            if supporting_value is None:
                issues.append(
                    f"No Mingomba estimate found in {source_id}."
                )

            elif claim != supporting_value:
                issues.append(
                    f"Claim {claim} does not match "
                    f"source {source_id}: {supporting_value}."
                )

    return {
        "checked": bool(checks),
        "supported": not issues if checks else None,
        "checks": checks,
        "issues": issues,
        "reason": (
            None
            if checks
            else "No supported claim type was detected."
        ),
    }
