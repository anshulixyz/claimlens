"""Schema coercion — including the P0 regression (substring snap must not flip meaning)."""

from evidence_review.schema import (
    CLAIM_STATUS,
    ISSUE_TYPE,
    OBJECT_PART,
    OUTPUT_COLUMNS,
    _snap,
    coerce_row,
)


def test_claim_status_fails_closed_not_supported():
    # P0: "unsupported" must NOT snap to "supported"
    assert (
        _snap("unsupported", CLAIM_STATUS, "not_enough_information", fuzzy=False)
        == "not_enough_information"
    )
    assert (
        coerce_row({"claim_status": "unsupported by the evidence"}, "car")["claim_status"]
        == "not_enough_information"
    )


def test_no_dangerous_substring_snaps():
    assert _snap("indoor", OBJECT_PART["car"], "unknown") == "unknown"  # not "door"
    assert _snap("transport", OBJECT_PART["laptop"], "unknown") == "unknown"  # not "port"
    assert _snap("dental", ISSUE_TYPE, "unknown") == "unknown"  # not "dent"


def test_legit_matches_still_work():
    assert _snap("front bumper area", OBJECT_PART["car"], "unknown") == "front_bumper"
    assert _snap("shattered_glass", ISSUE_TYPE, "unknown") == "glass_shatter"
    assert _snap("supported", CLAIM_STATUS, "not_enough_information", fuzzy=False) == "supported"


def test_coerce_row_always_legal():
    row = coerce_row(
        {
            "claim_status": "garbage",
            "issue_type": "nope",
            "object_part": "weird",
            "severity": "??",
            "risk_flags": "blah;none",
        },
        "laptop",
    )
    assert row["claim_status"] in CLAIM_STATUS
    assert row["issue_type"] in ISSUE_TYPE
    assert row["object_part"] in OBJECT_PART["laptop"]
    assert row["severity"] in {"none", "low", "medium", "high", "unknown"}
    # unknown flags drop to 'none'
    assert row["risk_flags"] == "none"


def test_output_columns_exact():
    assert OUTPUT_COLUMNS[:4] == ["user_id", "image_paths", "user_claim", "claim_object"]
    assert OUTPUT_COLUMNS[-1] == "severity"
    assert len(OUTPUT_COLUMNS) == 14
