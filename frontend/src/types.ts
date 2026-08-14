export interface KnowledgeBase {
  id: string
  name: string
  description: string | null
  is_active: boolean
  embedding_model: string
  embedding_dimension: number
  document_count: number
  created_at: string
  updated_at: string
}

export interface DocumentRecord {
  id: string
  knowledge_base_id: string
  filename: string
  content_type: string
  size_bytes: number
  status: 'pending' | 'processing' | 'completed' | 'failed'
  element_count: number
  chunk_count: number
  error_message: string | null
  processed_at: string | null
  created_at: string
  updated_at: string
}

export interface Citation {
  chunk_id: string
  document_id: string
  rank: number
  score: number
  quote?: string
  chunk_type?: string
  sequence_no?: number
  metadata?: Record<string, unknown>
}

export type RichTextBlock = {
  id: string
  type: 'heading' | 'lead' | 'paragraph' | 'callout'
  text: string
  level?: number
  tone?: 'info' | 'warning'
  source_ranks?: number[]
}

export type RichListBlock = {
  id: string
  type: 'list'
  style: 'ordered' | 'bullet'
  items: string[]
  source_ranks?: number[]
}

export type RichImageBlock = {
  id: string
  type: 'image'
  document_id: string
  sequence_no: number
  caption: string
  source_rank?: number
  source_label: string
  relation: 'direct' | 'nearby'
  alt: string
}

export type RichBlock = RichTextBlock | RichListBlock | RichImageBlock

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  citations?: Citation[]
  content_blocks?: RichBlock[]
  media_blocks?: RichImageBlock[]
  status_text?: string
  streaming?: boolean
  error?: boolean
}

export interface Conversation {
  id: string
  knowledge_base_id: string
  title: string
  created_at: string
  updated_at: string
}
