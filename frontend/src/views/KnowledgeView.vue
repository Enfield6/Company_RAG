<script setup lang="ts">
import { onUnmounted, ref } from 'vue'
import { Check, Database, FileText, LoaderCircle, Plus, UploadCloud, X } from '@lucide/vue'
import { useKnowledgeStore } from '../stores/knowledge'

const knowledge = useKnowledgeStore()
const creating = ref(false)
const name = ref('')
const description = ref('')
const dragging = ref(false)
const uploading = ref(false)
const notice = ref('')
const error = ref('')
let pollTimer: number | undefined
const supportedExtensions = ['.docx', '.doc', '.pdf', '.pptx', '.ppt', '.md', '.markdown', '.txt']
const fileAccept = supportedExtensions.join(',')

async function createKnowledgeBase() {
  if (!name.value.trim()) return
  error.value = ''
  try {
    await knowledge.create(name.value.trim(), description.value.trim())
    name.value = ''
    description.value = ''
    creating.value = false
    notice.value = '知识库已创建'
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '创建失败'
  }
}

async function upload(files: FileList | File[]) {
  const file = Array.from(files)[0]
  if (!file) return
  if (!supportedExtensions.some((extension) => file.name.toLowerCase().endsWith(extension))) {
    error.value = '支持 Word、PDF、PPT、Markdown 和 TXT 文件'
    return
  }
  uploading.value = true
  error.value = ''
  try {
    await knowledge.upload(file)
    notice.value = `${file.name} 已进入处理队列`
    startPolling()
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '上传失败'
  } finally {
    uploading.value = false
  }
}

function handleDrop(event: DragEvent) {
  dragging.value = false
  if (event.dataTransfer?.files) void upload(event.dataTransfer.files)
}

function startPolling() {
  if (pollTimer) window.clearInterval(pollTimer)
  pollTimer = window.setInterval(async () => {
    await knowledge.loadDocuments()
    const activeJobs = knowledge.documents.some((doc) => ['pending', 'processing'].includes(doc.status))
    if (!activeJobs && pollTimer) window.clearInterval(pollTimer)
  }, 2500)
}

function formatSize(bytes: number) {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

onUnmounted(() => {
  if (pollTimer) window.clearInterval(pollTimer)
})
</script>

<template>
  <section class="knowledge-view">
    <header class="page-header">
      <div>
        <span class="eyebrow">KNOWLEDGE CONTROL</span>
        <h1>知识库管理</h1>
        <p>管理文档、观察解析状态，并为每类业务资料建立独立检索边界。</p>
      </div>
      <button class="primary-button" @click="creating = !creating">
        <Plus :size="17" /> 新建知识库
      </button>
    </header>

    <div v-if="notice || error" class="notice" :class="{ 'notice--error': error }">
      <Check v-if="!error" :size="17" />
      <X v-else :size="17" />
      {{ error || notice }}
      <button aria-label="关闭提示" @click="notice = ''; error = ''"><X :size="15" /></button>
    </div>

    <form v-if="creating" class="create-card" @submit.prevent="createKnowledgeBase">
      <div>
        <label for="kb-name">名称</label>
        <input id="kb-name" v-model="name" maxlength="120" placeholder="例如：人力资源制度" autofocus />
      </div>
      <div>
        <label for="kb-description">说明</label>
        <input id="kb-description" v-model="description" placeholder="资料范围、负责人或使用场景" />
      </div>
      <button class="primary-button" type="submit" :disabled="!name.trim()">创建</button>
    </form>

    <div class="kb-tabs" role="tablist" aria-label="知识库列表">
      <button
        v-for="item in knowledge.items"
        :key="item.id"
        :class="{ active: item.id === knowledge.activeId }"
        @click="knowledge.setActive(item.id)"
      >
        <span><Database :size="16" />{{ item.name }}</span>
        <small>{{ item.document_count }} 份文档</small>
      </button>
    </div>

    <div v-if="knowledge.active" class="knowledge-grid">
      <section class="content-card upload-section">
        <div class="card-title">
          <div>
            <span class="card-icon"><UploadCloud :size="19" /></span>
            <div>
              <h2>添加资料</h2>
              <p>保留页码、标题和图文关系，并与相邻内容一起建立索引。</p>
            </div>
          </div>
        </div>
        <label
          class="drop-zone"
          :class="{ dragging, disabled: uploading }"
          @dragenter.prevent="dragging = true"
          @dragover.prevent
          @dragleave.prevent="dragging = false"
          @drop.prevent="handleDrop"
        >
          <LoaderCircle v-if="uploading" class="spin" :size="30" />
          <UploadCloud v-else :size="30" />
          <strong>{{ uploading ? '正在上传…' : '拖入文档，或点击选择' }}</strong>
          <span>支持 Word、PDF、PPT、Markdown、TXT，单文件不超过 100 MB</span>
          <input
            type="file"
            :accept="fileAccept"
            :disabled="uploading"
            @change="upload(($event.target as HTMLInputElement).files || [])"
          />
        </label>
      </section>

      <section class="content-card documents-section">
        <div class="card-title">
          <div>
            <span class="card-icon"><FileText :size="19" /></span>
            <div>
              <h2>文档处理状态</h2>
              <p>{{ knowledge.active.description || '暂无知识库说明' }}</p>
            </div>
          </div>
          <button class="secondary-button" @click="knowledge.loadDocuments">刷新</button>
        </div>

        <div v-if="knowledge.documents.length" class="document-list">
          <article v-for="document in knowledge.documents" :key="document.id" class="document-row">
            <span class="file-mark"><FileText :size="20" /></span>
            <div class="document-main">
              <strong>{{ document.filename }}</strong>
              <span>{{ formatSize(document.size_bytes) }} · {{ document.chunk_count }} 个检索块</span>
              <small v-if="document.error_message">{{ document.error_message }}</small>
            </div>
            <span class="status-pill" :class="`status-pill--${document.status}`">
              <LoaderCircle v-if="['pending', 'processing'].includes(document.status)" class="spin" :size="13" />
              {{
                {
                  pending: '等待处理',
                  processing: '解析中',
                  completed: '可检索',
                  failed: '失败',
                }[document.status]
              }}
            </span>
          </article>
        </div>
        <div v-else class="empty-documents">
          <FileText :size="27" />
          <strong>还没有文档</strong>
          <span>上传第一份文档后，解析进度会显示在这里。</span>
        </div>
      </section>
    </div>

    <div v-else class="empty-kb">
      <Database :size="34" />
      <h2>创建第一个知识库</h2>
      <p>建议按权限域或业务主题拆分，例如人事制度、产品资料、项目档案。</p>
      <button class="primary-button" @click="creating = true">开始创建</button>
    </div>
  </section>
</template>
