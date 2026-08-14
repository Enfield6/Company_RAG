import pymupdf
from PIL import Image

from app.documents.pdf_parser import PdfParser


def test_pdf_parser_preserves_page_text_and_image_neighborhood(tmp_path) -> None:
    image_path = tmp_path / "flow.png"
    Image.new("RGB", (80, 50), (16, 163, 127)).save(image_path)
    path = tmp_path / "guide.pdf"
    document = pymupdf.open()
    page = document.new_page(width=400, height=600)
    page.insert_text((40, 60), "Prepare server", fontsize=14)
    page.insert_image(pymupdf.Rect(40, 100, 200, 200), filename=str(image_path))
    page.insert_text((40, 250), "Check health status", fontsize=14)
    document.save(path)
    document.close()

    elements = PdfParser().parse(path)
    image = next(element for element in elements if element.kind == "image")

    assert [element.kind for element in elements] == ["text", "image", "text"]
    assert image.heading_path == ["第 1 页"]
    assert image.metadata["previous_text"] == "Prepare server"
    assert image.metadata["next_text"] == "Check health status"
    assert image.image_content_type == "image/png"


def test_pdf_parser_renders_empty_or_scanned_page_for_vision(tmp_path) -> None:
    path = tmp_path / "scan.pdf"
    document = pymupdf.open()
    document.new_page(width=300, height=300)
    document.save(path)
    document.close()

    elements = PdfParser().parse(path)

    assert len(elements) == 1
    assert elements[0].kind == "image"
    assert elements[0].metadata["scan_fallback"] is True
    assert elements[0].image_bytes
