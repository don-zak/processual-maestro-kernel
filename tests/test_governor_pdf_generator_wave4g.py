from __future__ import annotations

from dataclasses import dataclass

import processual_api.cgt_governor.reports.pdf_generator as pdf_generator


@dataclass
class _FakeParagraph:
    text: str


class _FakeTable:
    def __init__(self, data, colWidths=None):
        self.data = data
        self.col_widths = colWidths
        self.styles = []

    def setStyle(self, style) -> None:
        self.styles.append(style)


class _FakeDoc:
    def __init__(self, buffer, **kwargs):
        self.buffer = buffer
        self.kwargs = kwargs
        self.title = None
        self.author = None
        self.subject = None
        self.elements = None

    def build(self, elements) -> None:
        self.elements = list(elements)
        self.buffer.write(b"%PDF-fake")


def _install_reportlab_doubles(monkeypatch):
    docs = []

    def fake_doc(buffer, **kwargs):
        doc = _FakeDoc(buffer, **kwargs)
        docs.append(doc)
        return doc

    monkeypatch.setattr(pdf_generator, "SimpleDocTemplate", fake_doc)
    monkeypatch.setattr(pdf_generator, "Paragraph", lambda text, style: _FakeParagraph(text))
    monkeypatch.setattr(pdf_generator, "Spacer", lambda width, height: ("spacer", width, height))
    monkeypatch.setattr(pdf_generator, "Table", _FakeTable)
    return docs


def _paragraph_texts(elements):
    return [item.text for item in elements if isinstance(item, _FakeParagraph)]


def _tables(elements):
    return [item for item in elements if isinstance(item, _FakeTable)]


def test_generate_governance_pdf_builds_english_report_with_optional_sections(monkeypatch) -> None:
    docs = _install_reportlab_doubles(monkeypatch)
    evaluation = {
        "rank": "stable",
        "reward": 0.875,
        "policy": "accept",
        "policy_label": "Accept response",
        "ts": "2026-08-12T20:00:00+00:00",
        "fate_vector": {
            "stability": 0.9,
            "hybridity": 0.2,
            "distortion": 0.1,
            "extinction": 0.0,
            "collapse": 0.05,
            "flourishing": 0.8,
            "transient": 0.3,
        },
        "repair_prompt": "Tighten the answer before release.",
    }

    result = pdf_generator.generate_governance_pdf(
        evaluation,
        language="en",
        signature="abc123",
    )

    assert result == b"%PDF-fake"
    doc = docs[0]
    assert doc.title == "CGT Governance Report"
    assert doc.author == "Processual Maestro Kernel v2.0.0"
    assert doc.subject == "CGT Governance Report — stable"

    texts = _paragraph_texts(doc.elements)
    assert "CGT Governance Report" in texts
    assert any("<b>Date:</b> 2026-08-12T20:00:00+00:00" in text for text in texts)
    assert "Fate Vector" in texts
    assert "Repair Prompt" in texts
    assert "Tighten the answer before release." in texts
    assert any("<b>SHA3-256 Signature:</b><br/>abc123" == text for text in texts)
    assert any("Signed with Processual Crypto Envelope v2.0.0" in text for text in texts)

    tables = _tables(doc.elements)
    meta_table = tables[0]
    assert meta_table.data[0][1].text == "stable"
    assert meta_table.data[1][1].text == "0.875"
    assert meta_table.data[2][1].text == "Accept response"

    fate_table = tables[1]
    formatted_values = [row[1] for row in fate_table.data[1:]]
    assert formatted_values == ["0.9000", "0.2000", "0.1000", "0.0000", "0.0500", "0.8000", "0.3000"]


def test_generate_governance_pdf_builds_arabic_labels_and_policy_fallback(monkeypatch) -> None:
    docs = _install_reportlab_doubles(monkeypatch)
    evaluation = {
        "rank": "hybrid",
        "reward": 0.4,
        "policy": "repair_scaffold",
        "ts": "2026-08-12T20:05:00+00:00",
        "fate_vector": {"stability": 0.4, "transient": 0.6},
    }

    result = pdf_generator.generate_governance_pdf(evaluation, language="ar")

    assert result == b"%PDF-fake"
    doc = docs[0]
    assert doc.title == "تقرير حوكمة CGT"
    assert doc.subject == "CGT Governance Report — hybrid"

    texts = _paragraph_texts(doc.elements)
    assert "تقرير حوكمة CGT" in texts
    assert any("<b>التاريخ:</b> 2026-08-12T20:05:00+00:00" in text for text in texts)
    assert "متجه المصير" in texts
    assert "مطالبة الإصلاح" not in texts
    assert not any("SHA3-256" in text for text in texts)

    tables = _tables(doc.elements)
    meta_table = tables[0]
    assert meta_table.data[2][1].text == "repair_scaffold"

    fate_table = tables[1]
    assert fate_table.data[0] == ["الاستقرار", "العابر"]
    assert fate_table.data[1][0].text == "الاستقرار"
    assert fate_table.data[1][1] == "0.4000"
    assert fate_table.data[-1][0].text == "العابر"
    assert fate_table.data[-1][1] == "0.6000"


def test_generate_governance_pdf_uses_defaults_for_missing_values(monkeypatch) -> None:
    docs = _install_reportlab_doubles(monkeypatch)

    result = pdf_generator.generate_governance_pdf({}, language="en")

    assert result == b"%PDF-fake"
    doc = docs[0]
    assert doc.subject == "CGT Governance Report — —"

    tables = _tables(doc.elements)
    meta_table = tables[0]
    assert meta_table.data[0][1].text == "—"
    assert meta_table.data[1][1].text == "0"
    assert meta_table.data[2][1].text == "—"

    fate_table = tables[1]
    assert all(row[1] == "0.0000" for row in fate_table.data[1:])
