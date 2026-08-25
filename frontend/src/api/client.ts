import type {
  Citation,
  Conversation,
  DocumentRecord,
  KnowledgeBase,
  RichBlock,
} from '../types'

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, init)
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    throw new Error(body?.detail || `请求失败 (${response.status})`)
  }
  return response.json() as Promise<T>
}

export const api = {
  listKnowledgeBases: () => request<KnowledgeBase[]>('/knowledge-bases'),
  createKnowledgeBase: (name: string, description?: string) =>
    request<KnowledgeBase>('/knowledge-bases', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, description: description || null }),
    }),
  listDocuments: (knowledgeBaseId: string) =>
    request<DocumentRecord[]>(`/knowledge-bases/${knowledgeBaseId}/documents`),
  uploadDocument: async (knowledgeBaseId: string, file: File) => {
    const body = new FormData()
    body.append('file', file)
    return request<{ document: DocumentRecord; job_id: string }>(
      `/knowledge-bases/${knowledgeBaseId}/documents`,
      { method: 'POST', body },
    )
  },
  listConversations: (knowledgeBaseId?: string) =>
    request<Conversation[]>(
      `/chat/conversations${knowledgeBaseId ? `?knowledge_base_id=${knowledgeBaseId}` : ''}`,
    ),
  getConversation: (conversationId: string) =>
    request<{
      id: string
      messages: Array<{
        id: string
        role: 'user' | 'assistant'
        content: string
        citations?: Citation[]
        content_blocks?: RichBlock[]
      }>
    }>(`/chat/conversations/${conversationId}`),
}

type StreamHandlers = {
  onMeta: (data: { conversation_id: string }) => void
  onStatus: (data: { stage: string; message: string }) => void
  onToken: (data: { content: string }) => void
  onRich: (data: { blocks: RichBlock[] }) => void
  onCitations: (data: Citation[]) => void
  onDone: (data: { message_id: string }) => void
  onError: (data: { message: string }) => void
}

export async function streamChat(
  payload: { knowledge_base_id: string; question: string; conversation_id?: string },
  handlers: StreamHandlers,
): Promise<void> {
  const response = await fetch(`${API_BASE}/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: JSON.stringify(payload),
  })
  if (!response.ok || !response.body) {
    const body = await response.json().catch(() => null)
    throw new Error(body?.detail || `问答请求失败 (${response.status})`)
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  const dispatch = (block: string): string | undefined => {
    let event = 'message'
    const dataLines: string[] = []
    for (const line of block.split(/\r?\n/)) {
      if (line.startsWith('event:')) event = line.slice(6).trim()
      if (line.startsWith('data:')) dataLines.push(line.slice(5).trim())
    }
    if (!dataLines.length) return undefined
    const data = JSON.parse(dataLines.join('\n'))
    if (event === 'meta') handlers.onMeta(data)
    if (event === 'status') handlers.onStatus(data)
    if (event === 'token') handlers.onToken(data)
    if (event === 'rich') handlers.onRich(data)
    if (event === 'citations') handlers.onCitations(data)
    if (event === 'done') handlers.onDone(data)
    if (event === 'error') handlers.onError(data)
    return event
  }

  while (true) {
    const { value, done } = await reader.read()
    buffer += decoder.decode(value, { stream: !done })
    const blocks = buffer.split(/\r?\n\r?\n/)
    buffer = blocks.pop() || ''
    for (const block of blocks) {
      const event = dispatch(block)
      if (event === 'rich') {
        await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()))
      }
    }
    if (done) break
  }
  if (buffer.trim()) dispatch(buffer)
}

export function documentImageUrl(documentId: string, sequenceNo: number): string {
  return `${API_BASE}/documents/${documentId}/elements/${sequenceNo}/image`
}
