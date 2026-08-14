import os
import shutil
import subprocess
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


class OfficeConverter:
    def __init__(self, executable: str | None = None) -> None:
        self.executable = executable or shutil.which("soffice") or shutil.which("libreoffice")

    @property
    def available(self) -> bool:
        return bool(self.executable)

    @contextmanager
    def convert(self, source: Path, target_extension: str) -> Iterator[Path]:
        if not self.executable:
            raise RuntimeError(
                f"处理 {source.suffix.lower()} 需要 LibreOffice；"
                "请安装 LibreOffice，或先转换为新版 Office 格式后上传。"
            )
        target_extension = target_extension.lower().lstrip(".")
        with tempfile.TemporaryDirectory(prefix="company-rag-office-") as temp_dir:
            output_dir = Path(temp_dir)
            profile_dir = output_dir / "profile"
            profile_dir.mkdir()
            environment = os.environ.copy()
            environment["HOME"] = temp_dir
            command = [
                self.executable,
                "--headless",
                f"-env:UserInstallation={profile_dir.as_uri()}",
                "--convert-to",
                target_extension,
                "--outdir",
                str(output_dir),
                str(source),
            ]
            result = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=120,
                env=environment,
            )
            converted = output_dir / f"{source.stem}.{target_extension}"
            if result.returncode or not converted.exists():
                details = (result.stderr or result.stdout).strip()[-1000:]
                raise RuntimeError(
                    f"LibreOffice 无法将 {source.name} 转换为 {target_extension}"
                    + (f"：{details}" if details else "。")
                )
            yield converted
