from ingestforge.core.contracts import ArticleObject, MultilingualText, SourceRef, StandardPackage
from ingestforge.datasets.data_card import build_dataset_card
from ingestforge.observability.provenance import ProvenanceLedger


def test_provenance_ledger(tmp_path):
    ledger = ProvenanceLedger(tmp_path / "prov.jsonl")
    rid = ledger.append(entity="e", activity="fetch", agent="test")
    assert rid.startswith("prov_") and (tmp_path / "prov.jsonl").read_text()


def test_data_card():
    p = StandardPackage(
        source_refs=[SourceRef(url="https://example.com")],
        article=ArticleObject(title=MultilingualText(en="T"), body=MultilingualText(en="B")),
    )
    card = build_dataset_card(p)
    assert card["license_review_status"] == "needs_review"
