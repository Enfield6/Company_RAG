from app.documents.markdown_parser import MarkdownParser
from app.documents.text_parser import PlainTextParser


def test_markdown_parser_preserves_heading_path_and_content(tmp_path) -> None:
    path = tmp_path / "guide.md"
    path.write_text(
        "# 部署指南\n\n准备服务器。\n\n## 检查项\n\n- API 正常\n- 数据库正常\n",
        encoding="utf-8",
    )

    elements = MarkdownParser().parse(path)

    assert [element.text for element in elements] == [
        "部署指南",
        "准备服务器。",
        "检查项",
        "- API 正常\n- 数据库正常",
    ]
    assert elements[-1].heading_path == ["部署指南", "检查项"]


def test_plain_text_parser_supports_gb18030_and_paragraphs(tmp_path) -> None:
    path = tmp_path / "制度.txt"
    path.write_bytes("第一条：提交申请。\n\n第二条：主管审批。".encode("gb18030"))

    elements = PlainTextParser().parse(path)

    assert [element.text for element in elements] == ["第一条：提交申请。", "第二条：主管审批。"]
