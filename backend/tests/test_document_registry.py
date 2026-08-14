import pytest

from app.documents.registry import SUPPORTED_DOCUMENT_TYPES, DocumentParserRegistry


def test_registry_declares_all_product_upload_formats() -> None:
    assert set(SUPPORTED_DOCUMENT_TYPES) == {
        ".docx",
        ".doc",
        ".pdf",
        ".pptx",
        ".ppt",
        ".md",
        ".markdown",
        ".txt",
    }


def test_registry_rejects_unknown_extension(tmp_path) -> None:
    path = tmp_path / "unknown.csv"
    path.write_text("a,b", encoding="utf-8")

    with pytest.raises(ValueError, match="不支持的文档格式"):
        DocumentParserRegistry().parse(path)
