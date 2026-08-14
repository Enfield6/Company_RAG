import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { api } from '../api/client'
import type { DocumentRecord, KnowledgeBase } from '../types'

export const useKnowledgeStore = defineStore('knowledge', () => {
  const items = ref<KnowledgeBase[]>([])
  const documents = ref<DocumentRecord[]>([])
  const activeId = ref(localStorage.getItem('activeKnowledgeBase') || '')
  const loading = ref(false)
  const error = ref('')
  const active = computed(() => items.value.find((item) => item.id === activeId.value) || null)

  async function load() {
    loading.value = true
    error.value = ''
    try {
      items.value = await api.listKnowledgeBases()
      if (!items.value.some((item) => item.id === activeId.value)) {
        activeId.value = items.value[0]?.id || ''
      }
      if (activeId.value) await loadDocuments()
    } catch (reason) {
      error.value = reason instanceof Error ? reason.message : '知识库加载失败'
    } finally {
      loading.value = false
    }
  }

  async function create(name: string, description?: string) {
    const item = await api.createKnowledgeBase(name, description)
    items.value.unshift(item)
    setActive(item.id)
    return item
  }

  function setActive(id: string) {
    activeId.value = id
    localStorage.setItem('activeKnowledgeBase', id)
    void loadDocuments()
  }

  async function loadDocuments() {
    if (!activeId.value) {
      documents.value = []
      return
    }
    documents.value = await api.listDocuments(activeId.value)
  }

  async function upload(file: File) {
    if (!activeId.value) throw new Error('请先选择知识库')
    const result = await api.uploadDocument(activeId.value, file)
    documents.value.unshift(result.document)
    return result
  }

  return { items, documents, activeId, active, loading, error, load, create, setActive, loadDocuments, upload }
})
