# Company AI 私有知识库问答系统

这是一个面向公司内网部署的 RAG 问答系统骨架。前端使用 Vue 3 + TypeScript，后端使用 FastAPI；LangChain 负责模型与提示词适配，LangGraph 编排问答流程，MySQL 保存业务数据，Milvus 保存可检索的图文语义向量。

当前版本重点打通了：创建知识库 → 上传 Word/PDF/PPT/Markdown/TXT → 按文档结构解析图文 → 向量化入库 → 流式问答 → 灵光式图文消息 → 展示原文引用。认证、权限、任务队列和对象存储已留出边界，但没有擅自绑定某一种公司基础设施。

## 1. 系统结构

```text
浏览器（Vue 3）
      │ HTTP / SSE
      ▼
FastAPI ─────────────── MySQL
  │                       ├─ 知识库/文档/解析任务
  │                       └─ 对话/消息/引用
  ├─ 多格式结构解析（Word/PDF/PPT/Markdown/TXT）
  ├─ 图片与页面语义增强（Qwen VLM）
  ├─ LangGraph: 检索 → 回答 → 引用 → 富内容编排
  ├─ 本地文件存储（可替换 MinIO/S3）
  └──────────────────── Milvus
                          └─ 文本/表格/图片语义块 + 元数据 + 向量
```

## 2. 多格式文档如何保留结构与图片关系

Milvus 是检索数据库，不适合充当原始文件仓库。因此系统不会把图片二进制直接塞进 Milvus。各格式先归一化为有序的 `text/table/image` 元素：

1. DOCX：按 OOXML 原始顺序提取段落、表格、图片和标题路径；
2. PDF：按页码与页内坐标合并文字和嵌入图片；扫描页整页渲染后交给视觉模型；
3. PPTX：提取标题、文本、表格和备注，并通过 LibreOffice 渲染整张幻灯片，保留图表、形状和图片的空间关系；
4. Markdown/TXT：保留 Markdown 标题层级或纯文本段落；
5. 旧版 `.doc/.ppt`：由 LibreOffice 转换为 `.docx/.pptx` 后复用同一解析链；
6. 图片原件或页面渲染图保存在文件存储，Qwen 结合相邻文字生成业务描述与 OCR；
7. “图片描述 + OCR + 前后文”生成向量，Milvus 元数据保存页码、标题、元素顺序和原图位置。

这种设计保留了“图在哪、图和哪段话有关”，同时让原图存储、向量模型和视觉模型都可以独立替换。

## 3. 图文消息输出

AI 回答不是直接渲染模型生成的 HTML，而是转换成白名单结构块：标题、导语、正文、列表、重点提示和图片。这样可以获得类似灵光 APP 的图文简报阅读体验，同时避免模型输出脚本、危险标签或不可控样式。

输出过程中依次显示：

1. 检索文字与图片的状态；
2. 增量回答文字；
3. 直接命中的文档图片，或距离引用段落不超过 12 个元素的相关配图；
4. 完整图文排版；
5. 可展开的引用原文和相似度。

图片会标注“直接命中”或“相关文档配图”，避免把邻近图片误报成直接证据。完整结构保存在消息的 `content_blocks` 中，重新打开历史对话仍会保持原排版。

## 4. 目录

```text
backend/
  app/api/           API 路由与依赖
  app/db/            SQLAlchemy 模型与会话
  app/documents/     多格式解析、Office 转换、结构化切块
  app/graph/         LangGraph 问答图
  app/services/      文件、向量、图片增强、摄取服务
  alembic/           MySQL 迁移
  tests/             后端测试
frontend/
  src/components/    对话、输入框、侧栏组件
  src/stores/        Pinia 状态
  src/views/         问答页、知识库管理页
docs/
  API.md             API 与 SSE 事件说明
  DATABASE_DESIGN.md MySQL 与 Milvus 设计
storage/uploads/     本地开发文件存储（不提交内容）
```

## 5. Docker 启动、关闭与局域网访问

这一节是一份可独立执行的日常运维手册。除“本地开发”一节外，所有命令都在项目根目录执行。

### 5.1 运行条件

- 已安装并启动 Docker Desktop / Docker Engine；
- 建议至少为 Docker 分配 8 GB 内存；
- 服务器可以访问阿里云百炼中国地域 API；
- 局域网同事能访问这台服务器，并且防火墙允许前端端口 `8080`；
- `3306`、`8000`、`8080`、`9000`、`9001`、`9091`、`19530` 没有被其他程序占用。

后端镜像包含 LibreOffice 和中文字体，用于旧版 Office 转换及 PPT 整页渲染，因此第一次构建时间较长。向量由在线 Qwen API 生成，不会在本地下载 embedding 模型。

先进入项目目录：

```bash
cd /Users/zsh/Desktop/Programming/Company_RAG
```

检查 Docker：

```bash
docker version
docker compose version
```

### 5.2 第一次启动

只在 `.env` 不存在时从模板创建，避免覆盖已经填写的 API Key：

```bash
test -f .env || cp .env.example .env
```

打开 `.env`，至少填写并检查以下内容：

```dotenv
QWEN_API_KEY=你的百炼API-Key
MYSQL_PASSWORD=请改成强密码
MYSQL_ROOT_PASSWORD=请改成另一个强密码
MYSQL_DSN=mysql+asyncmy://company_rag:与MYSQL_PASSWORD相同的密码@mysql:3306/company_rag?charset=utf8mb4
DEBUG=false
```

注意：

- `MYSQL_PASSWORD` 与 `MYSQL_DSN` 中的密码必须相同；
- `.env` 只保存在当前项目，不要提交到 Git；
- 不要把本项目 `.env` 软链接到其他项目，否则任一项目重建配置时都可能覆盖另一边的密钥；
- 不要在终端、截图、聊天记录或前端代码中打印 API Key。

先检查 Compose 配置能否正确解析，再构建并后台启动：

```bash
docker compose config --quiet
docker compose up --build -d
```

第一次启动通常需要等待 MySQL、MinIO 和 Milvus 健康检查完成。查看状态：

```bash
docker compose ps
```

所有服务正常后，`STATUS` 应显示为 `Up` 或 `healthy`。继续验证：

```bash
curl http://localhost:8000/api/v1/health/live
curl http://localhost:8000/api/v1/health/ready
```

### 5.3 访问地址

本机访问：

- Web：<http://localhost:8080>
- FastAPI Swagger：<http://localhost:8000/docs>
- Milvus WebUI：<http://localhost:9091/webui/>
- 存活检查：<http://localhost:8000/api/v1/health/live>
- 就绪检查：<http://localhost:8000/api/v1/health/ready>

同一局域网的同事应使用运行 Docker 的服务器 IP，而不是 `localhost`。macOS 可执行：

```bash
ipconfig getifaddr en0
```

假设返回 `192.168.19.200`，同事访问：

```text
http://192.168.19.200:8080
```

若无法访问，依次检查：

1. 同事和服务器是否处于同一局域网或可互通 VLAN；
2. Wi-Fi 是否开启了“客户端隔离”；
3. macOS / Windows / Linux 防火墙是否允许 Docker 和 TCP `8080`；
4. `docker compose ps` 中 `frontend` 是否正常；
5. 服务器 IP 是否因 DHCP 重新分配而变化。长期使用建议在路由器中为服务器保留固定 IP。

前端 Nginx 会通过 Docker 内网把 `/api` 转发到 FastAPI，浏览器不会接触 Qwen API Key。同事只需要 Web 地址，不需要访问 MySQL、Milvus、MinIO 或 FastAPI 端口。

### 5.4 日常启动

已经完成过第一次构建后，普通启动使用：

```bash
cd /Users/zsh/Desktop/Programming/Company_RAG
docker compose up -d
docker compose ps
```

修改了 Python、Vue、依赖文件或 Dockerfile 后，需要重新构建：

```bash
docker compose up --build -d
```

只重启应用层、不重启数据库和向量库：

```bash
docker compose restart backend frontend
```

修改 `.env` 后，`restart` 不会重新读取全部容器环境变量，应重新创建应用容器：

```bash
docker compose up -d --force-recreate backend frontend
```

### 5.5 查看日志与排错

查看所有服务最近日志：

```bash
docker compose logs --tail=200
```

持续跟踪前后端日志，按 `Ctrl+C` 仅退出日志查看，不会停止容器：

```bash
docker compose logs -f --tail=200 backend frontend
```

单独查看摄取、模型或数据库问题：

```bash
docker compose logs --tail=300 backend
docker compose logs --tail=200 mysql
docker compose logs --tail=200 milvus
```

发现端口占用时，可先查占用者：

```bash
lsof -nP -iTCP:3306 -sTCP:LISTEN
lsof -nP -iTCP:8000 -sTCP:LISTEN
lsof -nP -iTCP:8080 -sTCP:LISTEN
lsof -nP -iTCP:19530 -sTCP:LISTEN
docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Ports}}'
```

如果之前通过终端运行了 `uvicorn` 或 `npm run dev`，回到对应终端按 `Ctrl+C` 正常停止后再启动 Compose。若之前单独启动过 MySQL 或 Milvus，请先确认数据位置和备份，再用原来的启动方式停止它们；不要为了释放端口直接删除容器或数据目录。

### 5.6 正确关闭项目

临时停止但保留现有容器，下一次启动最快：

```bash
docker compose stop
```

重新启动这些容器：

```bash
docker compose start
```

停止并删除应用容器和 Compose 网络，但保留 MySQL、Milvus、MinIO 数据卷：

```bash
docker compose down
```

日常关闭推荐使用 `docker compose stop`；需要重建容器或修改 Compose 配置时使用 `docker compose down`。

禁止在有用数据上执行：

```bash
docker compose down -v
```

`-v` 会删除 MySQL、Milvus、MinIO 和 etcd 数据卷，知识库、对话、引用和向量数据可能无法恢复。只有明确要清空全部 Docker 数据并且已经备份时才能使用。

项目上传文件保存在宿主机的 `storage/uploads/`，数据库与向量数据保存在 Docker 命名卷中。可用下面的命令查看卷：

```bash
docker volume ls | grep company
```

### 5.7 从当前本地开发环境切换到 Docker

Docker Compose 中的 MySQL 和 Milvus 使用独立数据卷，不会自动读取宿主机 MySQL 或另一套 Milvus 容器的数据。直接启动一套全新的 Compose 环境时，页面可能是空的，这是数据隔离而不是数据丢失。

切换前应：

1. 停止继续上传新文档；
2. 备份当前 MySQL；
3. 保留整个 `storage/uploads/`；
4. 导出或重建 Milvus collection；数据量较小时，最稳妥的方法是在新环境重新上传原文档，让系统重新解析并生成向量；
5. 完成验证后再停止旧环境，不要同时让两套应用写入同一份数据。

### 5.8 局域网开放前的安全检查

当前骨架还没有登录与知识库权限控制。只要能访问 `8080`，用户就可以看到知识库、历史对话、引用内容并上传文档。因此：

- 仅在受控公司内网或测试 VLAN 开放；
- 防火墙只允许需要的网段访问 `8080`；
- 修改示例中的数据库密码；
- 不要把 `3306`、`19530`、`9000` 等数据服务端口开放到非受控网络；
- 正式推广前应增加 OIDC / LDAP / 企业微信 / 钉钉 / 自有 SSO，以及知识库级 ACL、审计日志和速率限制；
- 需要跨办公地点或公网访问时，应使用 HTTPS、VPN 或公司网关，不要直接把 Docker 端口暴露到公网。

## 6. 通义千问模型配置

当前默认模型如下：

| 用途 | 模型 | 选择原因 |
|---|---|---|
| RAG 回答 | `qwen3.5-omni-plus` | 支持文本、图片、音频和视频输入，也支持工具调用；后续扩展多模态提问时不用更换主模型 |
| 文档图片/页面理解与 OCR | `qwen3.5-omni-plus` | 与回答模型共用一个 API 和消息协议，可结合页码、标题和前后文生成描述 |
| 文本/图片语义描述向量化 | `text-embedding-v4` | 面向文本检索的 Qwen3 embedding；支持自定义维度，当前固定为 1024 维 |

模型能力与限制以阿里云官方的 [`qwen3.5-omni-plus` 文档](https://help.aliyun.com/zh/model-studio/qwen3-5-omni-plus)和[向量模型列表](https://help.aliyun.com/zh/model-studio/embedding-rerank-model)为准。

三种能力都通过百炼的 OpenAI-compatible 接口调用，只需配置一个 `QWEN_API_KEY`：

```dotenv
QWEN_API_KEY=sk-请填写百炼API-Key
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL=qwen3.5-omni-plus
VISION_MODEL=qwen3.5-omni-plus
EMBEDDING_MODEL=text-embedding-v4
EMBEDDING_DIMENSION=1024
```

不要提交 `.env`，也不要把两个项目的 `.env` 做成软链接。需要复用同一个 Key 时，只把对应变量值填入本项目独立的 `.env`；这样修改、删除或重新生成任一项目配置时不会影响另一个项目。

`LLM_*`、`VISION_*` 和 `EMBEDDING_*` 的 URL/Key 仍可分别覆盖，便于以后切到公司网关。未配置 `QWEN_API_KEY` 时，文档向量化会明确失败；已有向量仍可检索，但回答会降级为返回相关原文片段。

重要配置：

| 变量 | 默认值 | 说明 |
|---|---|---|
| `MYSQL_DSN` | Compose 内部地址 | MySQL 异步连接串 |
| `MILVUS_URI` | `http://milvus:19530` | Milvus 地址 |
| `QWEN_API_KEY` | 无 | 百炼 API Key，回答、视觉理解与向量化共用 |
| `DASHSCOPE_BASE_URL` | 中国地域兼容接口 | 百炼 OpenAI-compatible Base URL |
| `LLM_MODEL` / `VISION_MODEL` | `qwen3.5-omni-plus` | 回答与图片语义理解模型 |
| `EMBEDDING_MODEL` | `text-embedding-v4` | 文本与图片描述的向量模型 |
| `EMBEDDING_DIMENSION` | `1024` | 必须和模型输出一致；变更需新建 collection |
| `UPLOAD_DIR` | `/app/storage/uploads` | 文件根目录 |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | `900` / `120` | 结构化切块字符数 |
| `RETRIEVAL_TOP_K` | `6` | 单次检索返回数 |

## 7. 本地开发

后端建议使用 Python 3.11 或 3.12：

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e './backend[dev]'
```

本地处理 `.doc/.ppt` 或把 PPTX 渲染为整页图片还需要安装 LibreOffice，并确保 `soffice` 在 `PATH` 中。没有 LibreOffice 时 `.docx/.pdf/.pptx/.md/.txt` 仍可解析，但 PPTX 会退回为文本、表格和内嵌图片抽取。

如果后端运行在宿主机，把 `.env` 中以下主机名改为本地端口：

```dotenv
MYSQL_DSN=mysql+asyncmy://company_rag:change-me@127.0.0.1:3306/company_rag?charset=utf8mb4
MILVUS_URI=http://127.0.0.1:19530
UPLOAD_DIR=storage/uploads
```

然后分别启动：

```bash
cd backend
alembic upgrade head
uvicorn app.main:app --reload
```

```bash
cd frontend
npm install
npm run dev
```

## 8. 测试与构建

```bash
cd backend
pytest
ruff check app tests

cd ../frontend
npm run type-check
npm run build
```

## 9. 当前边界与生产化清单

当前摄取任务使用 FastAPI 后台任务，适合搭骨架和单机验证；大量文档并发导入前应替换为 Celery、Dramatiq 或公司现有消息队列。生产落地前还需要确认：

- 认证方式：OIDC / LDAP / 企业微信 / 钉钉 / 自有 SSO；
- 权限粒度：知识库级、文档级还是段落级 ACL；
- 文件存储：公司 MinIO / S3 / NAS，以及备份和保留策略；
- 模型服务：百炼配额、并发、数据合规和调用审计，或后续迁移至公司内网推理服务；
- 文档范围：Excel、HTML、邮件和网页归档是否进入下一阶段；
- 安全：上传恶意文件扫描、审计日志、速率限制、密钥托管、传输加密。

API 细节见 [`docs/API.md`](docs/API.md)，数据结构见 [`docs/DATABASE_DESIGN.md`](docs/DATABASE_DESIGN.md)。
