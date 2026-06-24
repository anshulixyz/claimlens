"""End-to-end smoke: the mock tier produces a schema-conformant row offline.

Runs the full harness (Tier-0 CV -> intake -> mock perception -> mock judge ->
tools -> fusion -> coercion) with NO API keys, so CI is hermetic.
"""

from evidence_review import Config, Pipeline
from evidence_review import config as cfgmod
from evidence_review.schema import CLAIM_STATUS, OUTPUT_COLUMNS


def _have_sample():
    return (cfgmod.DATASET_DIR / "images" / "sample" / "case_001" / "img_1.jpg").exists()


def test_mock_pipeline_row_is_legal():
    cfg = Config(
        perception_provider="mock",
        perception_model="mock",
        judge_provider="mock",
        judge_model="mock",
    )
    pipe = Pipeline(cfg, use_cache=False, verbose=False)
    img = "images/sample/case_001/img_1.jpg" if _have_sample() else "images/test/nope/x.jpg"
    row = {
        "user_id": "user_001",
        "image_paths": img,
        "user_claim": "There is a dent on the rear bumper of my car.",
        "claim_object": "car",
    }
    out = pipe.process_rows([row])[0]
    # exact columns + order, all present
    assert list(out.keys()) == OUTPUT_COLUMNS
    assert out["claim_status"] in CLAIM_STATUS
    assert out["valid_image"] in {"true", "false"}
    assert out["evidence_standard_met"] in {"true", "false"}
    # input columns preserved
    assert out["user_id"] == "user_001" and out["claim_object"] == "car"


def test_registry_has_expected_tools():
    pipe = Pipeline(
        Config(perception_provider="mock", judge_provider="mock"), use_cache=False, verbose=False
    )
    names = [t["name"] for t in pipe.registry.manifest()]
    for expected in ["quality", "provenance", "forgery", "ocr_injection"]:
        assert expected in names
