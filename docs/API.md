# API 文档

## 约定

- Base URL：`/api/v1`
- 普通接口：`application/json`
- 上传：`multipart/form-data`
- 问答流：`text/event-stream`
- 当前骨架尚未接入认证；生产环境必须由网关或应用认证层补上用户身份和知识库权限校验。

FastAPI 同时在 `/docs` 提供可交互 OpenAPI 页面。

模型依赖：文档摄取需要 `QWEN_API_KEY` 调用 `text-embedding-v4`；图像语义增强和回答默认调用 `qwen3.5-omni-plus`。API 不接收也不返回模型密钥。

## 健康检查

### `GET /health/live`

只表示 Web 进程可响应。

```json
{"status":"ok"}
```

### `GET /health/ready`

检查 MySQL 和 Milvus。任一不可用返回 HTTP 503。

```json
{"status":"ok","mysql":"ok","milvus":"ok"}
```

## 知识库

### `POST /knowledge-bases`

```json
{
  "name": "人力资源制度",
  "description": "员工手册、考勤和审批规定"
}
```

成功：HTTP 201。

### `GET /knowledge-bases`

返回知识库列表，并包含 `document_count`。

### `GET /knowledge-bases/{knowledge_base_id}`

返回单个知识库；不存在时为 404。

## 文档

### `POST /knowledge-bases/{knowledge_base_id}/documents`

表单字段：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `file` | file | 是 | `.docx/.doc/.pdf/.pptx/.ppt/.md/.markdown/.txt`，默认最大 100 MB |

成功返回 HTTP 202，解析在后台继续：

```json
{
  "document": {
    "id": "uuid",
    "knowledge_base_id": "uuid",
    "filename": "员工手册.docx",
    "content_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "size_bytes": 345678,
    "status": "pending",
    "element_count": 0,
    "chunk_count": 0,
    "error_message": null,
    "processed_at": null,
    "created_at": "2026-08-13T10:00:00Z",
    "updated_at": "2026-08-13T10:00:00Z"
  },
  "job_id": "uuid"
}
```

常见错误：

- 404：知识库不存在；
- 409：同一知识库已有相同 SHA-256 的文件；
- 413：超过大小限制；
- 415：扩展名不在支持列表中；
- 后台失败：加密 PDF、损坏文件、没有可索引内容，或处理旧 Office 文件时服务器未安装 LibreOffice。失败原因写入文档的 `error_message`。

格式处理策略：

| 格式 | 结构保留方式 |
|---|---|
| DOCX | OOXML 段落、标题、表格、图片及前后文顺序 |
| DOC | LibreOffice 转 DOCX 后按相同流程处理 |
| PDF | 页码、页内坐标、文字块和嵌入图片；扫描页走整页视觉 OCR |
| PPTX | 标题、文本、表格、备注；可用 LibreOffice 时额外保存整页渲染图 |
| PPT | LibreOffice 转 PPTX 后按相同流程处理 |
| Markdown | ATX 标题层级、段落与代码块；外部图片只记录链接，不由服务端抓取 |
| TXT | UTF-8/UTF-16/GB18030 自动解码并按段落切分 |

### `GET /knowledge-bases/{knowledge_base_id}/documents`

返回文档列表。前端可轮询 `status`：`pending`、`processing`、`completed`、`failed`。

### `GET /documents/{document_id}`

返回文档状态与解析统计。

### `GET /documents/{document_id}/elements/{sequence_no}/image`

返回某个图片元素的原始图片，用于引用预览。

## 流式问答

### `POST /chat/stream`

请求：

```json
{
  "knowledge_base_id": "uuid",
  "question": "年假审批需要哪些步骤？",
  "conversation_id": null
}
```

首次提问不传 `conversation_id`；继续对话时回传 `meta` 事件中的 ID。

响应是 SSE。事件顺序：

```text
event: meta
data: {"conversation_id":"uuid"}

event: status
data: {"stage":"retrieving","message":"正在检索文字与相关图片"}

event: token
data: {"content":"根据员工手册"}

event: media
data: {"id":"block-2","type":"image","document_id":"...","sequence_no":8,"caption":"审批流程图","relation":"direct"}

event: rich
data: {"blocks":[{"id":"block-0","type":"heading","text":"审批流程"}, ...]}

event: citations
data: [{"chunk_id":"...","document_id":"...","rank":1,"score":0.91,...}]

event: done
data: {"message_id":"uuid"}
```

事件说明：

| 事件 | 说明 |
|---|---|
| `meta` | 本次对话 ID |
| `status` | 当前阶段和用户可读状态，如检索、图文编排 |
| `token` | 增量回答文本，可多次出现 |
| `media` | 在文字仍在输出时插入一张文档图片 |
| `rich` | 完整安全结构块；前端据此切换为图文简报布局 |
| `citations` | 检索引用；包含文档、块类型、顺序号和图片元数据 |
| `done` | 回答已持久化，给出消息 ID |
| `error` | 流内错误，格式为 `{"message":"..."}` |

`rich.blocks` 当前支持：`heading`、`lead`、`paragraph`、`list`、`callout`、`image`。前端只渲染这些白名单结构，不执行模型提供的 HTML。当前后端先完成 LangGraph 调用，再把结果分片为 SSE；后续模型服务确定后，可把生成节点替换为模型原生 token 流，前端协议无需变化。

说明：`token` 是后端对完整模型回答进行安全分片后的增量事件，目前不是 Qwen 原生 token 流；这一选择保证 `rich` 图文结构和持久化结果一致。

## 对话历史

### `GET /chat/conversations?knowledge_base_id={id}`

最多返回最近 100 条对话。

### `GET /chat/conversations/{conversation_id}`

返回对话及全部消息、消息引用。

## curl 示例

```bash
curl -X POST http://localhost:8000/api/v1/knowledge-bases \
  -H 'Content-Type: application/json' \
  -d '{"name":"产品知识","description":"内部产品资料"}'
```

```bash
curl -X POST "http://localhost:8000/api/v1/knowledge-bases/$KB_ID/documents" \
  -F 'file=@./产品手册.pdf'
```

```bash
curl -N -X POST http://localhost:8000/api/v1/chat/stream \
  -H 'Content-Type: application/json' \
  -d "{\"knowledge_base_id\":\"$KB_ID\",\"question\":\"产品如何部署？\"}"
```
