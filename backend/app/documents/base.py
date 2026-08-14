from pathlib import Path
from typing import Protocol

from app.documents.types import ParsedElement


class DocumentParser(Protocol):
    def parse(self, path: Path) -> list[ParsedElement]: ...


def append_element(elements: list[ParsedElement], element: ParsedElement) -> None:
    element.sequence_no = len(elements)
    elements.append(element)


def attach_image_neighborhood(elements: list[ParsedElement]) -> None:
    text_indexes = [
        index
        for index, element in enumerate(elements)
        if element.kind != "image" and element.text
    ]
    for index, element in enumerate(elements):
        if element.kind != "image":
            continue
        previous = next((item for item in reversed(text_indexes) if item < index), None)
        following = next((item for item in text_indexes if item > index), None)
        element.metadata["previous_text"] = (
            elements[previous].text if previous is not None else ""
        )
        element.metadata["next_text"] = (
            elements[following].text if following is not None else ""
        )
        element.metadata["previous_sequence"] = previous
        element.metadata["next_sequence"] = following
