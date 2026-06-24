"""Docs-stay-in-sync gate — fails CI when code & docs drift apart.

Enforces the working agreement in CURRENT.md (the parts a machine can check):
  - every registered Tool is documented somewhere under docs/
  - every registered provider/router model is named in MODEL_ROUTING.md
  - every docs/*.md is linked from the docs index (no orphan docs)
  - the output schema's column count matches what the docs claim (14)

These are structural, stable checks: adding a tool/model/doc without updating the
relevant doc breaks the build, which is the point.
"""

from pathlib import Path

from evidence_review.router import CATALOG
from evidence_review.schema import OUTPUT_COLUMNS
from evidence_review.tools import default_registry

DOCS = Path(__file__).resolve().parent.parent / "docs"


def _docs_blob() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in DOCS.glob("*.md")).lower()


def test_every_tool_is_documented():
    blob = _docs_blob()
    missing = [t["name"] for t in default_registry().manifest() if t["name"].lower() not in blob]
    assert not missing, (
        f"Tools not documented under docs/: {missing} — update TOOLS.md/SCENARIO_COVERAGE.md"
    )


def test_every_router_model_is_documented():
    routing = (DOCS / "MODEL_ROUTING.md").read_text(encoding="utf-8").lower()
    # mock is internal; every real catalog model must be named in the routing doc
    missing = [m.model for m in CATALOG if m.provider != "mock" and m.model.lower() not in routing]
    assert not missing, f"Router models not in MODEL_ROUTING.md: {missing}"


def test_every_doc_is_indexed():
    index = (DOCS / "README.md").read_text(encoding="utf-8")
    orphans = [p.name for p in DOCS.glob("*.md") if p.name != "README.md" and p.name not in index]
    assert not orphans, f"docs/ files not linked from docs/README.md: {orphans}"


def test_output_schema_matches_docs():
    assert len(OUTPUT_COLUMNS) == 14  # the contract the docs + problem statement assert
