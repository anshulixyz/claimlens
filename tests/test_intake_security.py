"""Intake admissibility protocol + input-security guards."""

from evidence_review import config as cfgmod
from evidence_review import dataio, intake


def test_missing_image_is_inadmissible():
    a = intake.assess(cfgmod.DATASET_DIR / "images" / "nope" / "missing.jpg", {})
    assert a.status == intake.Status.MISSING
    assert a.send_to_model is False and a.valid_image is False


def test_real_sample_image_ok():
    p = dataio.resolve_image("images/sample/case_001/img_1.jpg")
    if not p.exists():
        return  # dataset not present (e.g. in code.zip) — skip
    a = intake.assess(p, {"small_side": 400, "usable": True})
    assert a.status == intake.Status.OK and a.send_to_model is True


def test_path_traversal_rejected():
    p = dataio.resolve_image("../../../../etc/passwd")
    assert "__rejected_path__" in str(p)
    # and the resolved path stays inside the dataset dir
    assert str(p).startswith(str(cfgmod.DATASET_DIR.resolve()))


def test_register_custom_check():
    calls = {"n": 0}

    def block_all(path, raw, cv):
        calls["n"] += 1
        return intake.Status.BLOCKED, "policy"

    p = dataio.resolve_image("images/sample/case_001/img_1.jpg")
    intake.register_check(block_all)
    try:
        a = intake.assess(p, {})
        # custom check ran and decided the status (registry is extensible)
        if p.exists():
            assert calls["n"] >= 1 and a.status == intake.Status.BLOCKED
    finally:
        intake._CHECKS.pop()  # cleanup
