import re
import shutil
from pathlib import Path


class LocalFileStorage:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def save_document(self, document_id: str, filename: str, content: bytes) -> str:
        safe_name = self._safe_filename(filename)
        relative = Path(document_id) / "original" / safe_name
        return self._write(relative, content)

    def save_image(self, document_id: str, sequence_no: int, extension: str, content: bytes) -> str:
        safe_extension = extension if re.fullmatch(r"\.[a-zA-Z0-9]{1,8}", extension) else ".bin"
        relative = Path(document_id) / "images" / f"{sequence_no:06d}{safe_extension.lower()}"
        return self._write(relative, content)

    def resolve(self, stored_path: str) -> Path:
        candidate = (self.root / stored_path).resolve()
        if self.root not in candidate.parents:
            raise ValueError("Invalid storage path")
        return candidate

    def delete_document(self, document_id: str) -> None:
        target = self.resolve(document_id)
        if target.exists():
            shutil.rmtree(target)

    def prune_images(self, document_id: str, keep_paths: set[str]) -> None:
        """Remove generated image files that are no longer referenced after re-ingestion."""
        image_directory = self.resolve(f"{document_id}/images")
        if not image_directory.exists():
            return
        for path in image_directory.iterdir():
            relative_path = path.relative_to(self.root).as_posix()
            if path.is_file() and relative_path not in keep_paths:
                path.unlink()

    def _write(self, relative: Path, content: bytes) -> str:
        destination = self.root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
        return relative.as_posix()

    @staticmethod
    def _safe_filename(filename: str) -> str:
        clean = Path(filename).name
        clean = re.sub(r"[^\w.\-()\u4e00-\u9fff]+", "_", clean, flags=re.UNICODE)
        return clean[:255] or "document.docx"
