import { reactive, ref } from 'vue'
import { defineStore } from 'pinia'
import { api, streamChat } from '../api/client'
import type { ChatMessage, Conversation, RichBlock } from '../types'

export const useChatStore = defineStore('chat', () => {
  const messages = ref<ChatMessage[]>([])
  const conversations = ref<Conversation[]>([])
  const conversationId = ref<string>()
  const sending = ref(false)

  function newChat() {
    messages.value = []
    conversationId.value = undefined
  }

  async function loadConversations(knowledgeBaseId?: string) {
    conversations.value = await api.listConversations(knowledgeBaseId)
  }

  async function openConversation(id: string) {
    const result = await api.getConversation(id)
    conversationId.value = id
    messages.value = result.messages.map((item) => ({
      ...item,
      content_blocks: (item.content_blocks || []) as RichBlock[],
      citations: item.citations?.map((citation) => ({
        ...citation,
        chunk_type: citation.chunk_type || String(citation.metadata?.chunk_type || ''),
        sequence_no:
          citation.sequence_no ??
          (typeof citation.metadata?.sequence_no === 'number'
            ? citation.metadata.sequence_no
            : undefined),
      })),
    }))
  }

  async function send(question: string, knowledgeBaseId: string) {
    if (sending.value || !question.trim()) return
    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: question.trim(),
    }
    const assistantMessage = reactive<ChatMessage>({
      id: crypto.randomUUID(),
      role: 'assistant',
      content: '',
      citations: [],
      content_blocks: [],
      status_text: '正在理解问题',
      streaming: true,
    })
    messages.value.push(userMessage, assistantMessage)
    sending.value = true
    try {
      await streamChat(
        {
          knowledge_base_id: knowledgeBaseId,
          question: question.trim(),
          conversation_id: conversationId.value,
        },
        {
          onMeta: ({ conversation_id }) => {
            conversationId.value = conversation_id
          },
          onStatus: ({ message }) => {
            assistantMessage.status_text = message
          },
          onToken: ({ content }) => {
            assistantMessage.content += content
          },
          onRich: ({ blocks }) => {
            assistantMessage.content_blocks = blocks
            assistantMessage.status_text = '正在逐步生成图文回答'
          },
          onCitations: (citations) => {
            assistantMessage.citations = citations
          },
          onDone: ({ message_id }) => {
            assistantMessage.id = message_id
            assistantMessage.streaming = false
            assistantMessage.status_text = undefined
          },
          onError: ({ message }) => {
            assistantMessage.content = `抱歉，处理失败：${message}`
            assistantMessage.streaming = false
            assistantMessage.status_text = undefined
            assistantMessage.error = true
          },
        },
      )
      await loadConversations(knowledgeBaseId)
    } catch (reason) {
      assistantMessage.content = `抱歉，处理失败：${reason instanceof Error ? reason.message : '未知错误'}`
      assistantMessage.streaming = false
      assistantMessage.status_text = undefined
      assistantMessage.error = true
    } finally {
      sending.value = false
    }
  }

  return {
    messages,
    conversations,
    conversationId,
    sending,
    newChat,
    loadConversations,
    openConversation,
    send,
  }
})
