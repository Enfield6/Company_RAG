# 数据库设计文档

## 1. 存储职责

| 存储 | 保存内容 | 不保存内容 |
|---|---|---|
| MySQL 8 | 知识库、文档元数据、解析状态、元素位置、对话、消息、引用 | 高维向量、图片二进制 |
| Milvus | 检索块、过滤字段、结构元数据、1024 维向量 | 用户/权限、任务真相、原始文件 |
| 文件存储 | 原始文档、抽取图片、PDF/PPT 页面渲染图 | 业务关系、向量 |

MySQL 是业务事实来源。Milvus 中的向量可以根据 MySQL 和文件原件重建。

## 2. 关系模型

```text
knowledge_bases 1 ── N documents 1 ── N document_elements
                         │
                         └────── 1 ── N ingestion_jobs

knowledge_bases 1 ── N conversations 1 ── N messages 1 ── N citations
                                                     │
                                                     └── N ── 1 documents
```

## 3. MySQL 表

### `knowledge_bases`

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | varchar(36) PK | UUID |
| `name` | varchar(120) | 名称 |
| `description` | text | 范围说明 |
| `is_active` | boolean | 软启用状态 |
| `embedding_model` | varchar(255) | 创建时使用的向量模型 |
| `embedding_dimension` | int | 向量维度 |
| `created_at`, `updated_at` | datetime | 审计时间 |

向量模型和维度写入知识库，是为了避免无感升级模型导致同一检索空间向量不兼容。

### `documents`

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | varchar(36) PK | 文档 ID |
| `knowledge_base_id` | varchar(36) FK | 所属知识库 |
| `filename`, `content_type` | varchar | 原文件信息 |
| `size_bytes` | bigint | 文件大小 |
| `sha256` | varchar(64) | 内容去重 |
| `storage_path` | varchar(1024) | 原文件位置 |
| `status` | varchar(32) | pending / processing / completed / failed |
| `element_count`, `chunk_count` | int | 解析统计 |
| `error_message` | text | 失败摘要 |
| `processed_at` | datetime | 完成时间 |

唯一约束：`(knowledge_base_id, sha256)`。索引：`(knowledge_base_id, status)`。

### `ingestion_jobs`

记录每次摄取任务的状态机：`queued → parsing → image_enrichment → chunking → embedding → vector_indexing → completed`。`attempts` 为未来队列重试保留。

### `document_elements`

这是保存不同文档格式统一逻辑结构的关键表。

| 字段 | 类型 | 说明 |
|---|---|---|
| `document_id`, `sequence_no` | FK + int | 文档内稳定顺序，组合唯一 |
| `kind` | varchar(32) | text / table / image |
| `text_content` | text | 段落或表格文本 |
| `heading_path` | JSON | 标题层级，如 `["第二章", "请假"]` |
| `image_path` | varchar(1024) | 抽取图片位置 |
| `image_caption`, `image_ocr` | text | 视觉模型结果或保底描述 |
| `relationship_id` | varchar(128) | DOCX/PPTX 关系 ID，或 PDF 页面图片稳定标识 |
| `element_metadata` | JSON | 前后元素序号、页码/幻灯片号、坐标、说明来源等 |

### `conversations` / `messages`

`conversations` 保存知识库边界和标题；`messages` 保存 user / assistant 消息、模型名及预留 token 统计。`messages.content_blocks` 是可空 JSON，保存经过后端白名单转换的标题、段落、列表、重点和图片结构，使历史消息可以稳定恢复图文排版，而不必重新调用模型。`user_id` 当前可空，接入 SSO 后应改为用户表或身份提供方 subject 的外键/稳定 ID。

### `citations`

| 字段 | 类型 | 说明 |
|---|---|---|
| `message_id` | FK | 助手消息 |
| `document_id` | FK | 来源文档 |
| `chunk_id` | varchar(64) | Milvus 主键 |
| `rank`, `score` | int / float | 排名与相似度 |
| `quote` | text | 当时返回的引用快照 |
| `citation_metadata` | JSON | 块类型、元素顺序、图片路径等 |

保存引用快照是为了在向量重新构建后仍能审计“当时依据了什么”。

## 4. Milvus Collection

默认 collection：`company_knowledge_chunks`。

| 字段 | Milvus 类型 | 说明 |
|---|---|---|
| `id` | VARCHAR(64), PK | chunk UUID |
| `knowledge_base_id` | VARCHAR(36) | 检索强制过滤 |
| `document_id` | VARCHAR(36) | 删除/重建过滤 |
| `chunk_type` | VARCHAR(32) | text / table / image |
| `sequence_no` | INT64 | 原文位置 |
| `content` | VARCHAR(65535) | 送入 embedding 的完整语义文本 |
| `metadata` | JSON | 标题路径、元素序号、图片位置等 |
| `embedding` | FLOAT_VECTOR(1024) | `text-embedding-v4` 生成的语义向量 |

索引：

- `embedding`：`AUTOINDEX + COSINE`；
- `knowledge_base_id`：`INVERTED`；
- `document_id`：`INVERTED`。

查询必须带 `knowledge_base_id` 过滤。接入文档级 ACL 后，还需要在检索前得到用户可访问文档集合，并把 ACL 过滤下推到 Milvus；不能只在生成答案后隐藏引用。

## 5. 一致性与重建

摄取流程先解析和向量化，再写 Milvus，最后提交 MySQL 元素与完成状态。如果末段失败，会尽力按 `document_id` 清理 Milvus；生产队列仍应增加幂等键、周期性孤儿清理和 outbox/reconciliation 任务。

推荐重建策略：

1. 暂停目标知识库写入；
2. 创建带版本号的新 collection；
3. 从 MySQL 元数据和文件存储重新解析/嵌入；
4. 校验数量与抽样召回；
5. 原子切换 collection 配置；
6. 保留旧 collection 一段回滚窗口。

## 6. 备份

- MySQL：全量备份 + binlog/PITR；
- 文件存储：版本控制或不可变备份；
- Milvus：可备份以缩短恢复时间，但不能替代 MySQL 和原文件；
- 配置与模型版本：随部署版本记录，尤其是 embedding 模型、维度、切块参数和视觉模型。

## 7. 当前模型与变更约束

- 新建知识库默认写入 `embedding_model=text-embedding-v4`、`embedding_dimension=1024`；
- 文本块和表格块直接向量化；图片块先由 `qwen3.5-omni-plus` 生成 caption/OCR，再把“图片描述 + OCR + 前后文”交给 `text-embedding-v4`；
- 图片二进制始终留在文件存储，Milvus 只保存可检索的语义表示和定位元数据；
- 不能把不同模型或不同维度的向量混入同一 collection。升级 embedding 模型时按第 5 节创建新 collection 并重建索引；
- 当前方案支持“用文字检索文档图片”。若以后需要以图片搜图片，再单独增加多模态向量字段或 collection，不能直接覆盖现有文本向量。
