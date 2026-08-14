<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { BookOpenCheck, FileSearch, Image, Sparkles } from '@lucide/vue'
import ChatMessage from '../components/ChatMessage.vue'
import PromptComposer from '../components/PromptComposer.vue'
import { useChatStore } from '../stores/chat'
import { useKnowledgeStore } from '../stores/knowledge'

const chat = useChatStore()
const knowledge = useKnowledgeStore()
const list = ref<HTMLElement>()
const composer = ref<InstanceType<typeof PromptComposer>>()
const ready = computed(() => Boolean(knowledge.activeId))

const suggestions = [
  { icon: BookOpenCheck, title: '总结制度', text: '请总结当前知识库中的核心制度，并列出员工最需要注意的事项。' },
  { icon: FileSearch, title: '查找依据', text: '这套知识库里有哪些文档提到了审批流程？请给出引用。' },
  { icon: Image, title: '理解图表', text: '请查找文档图片或图表中的关键信息，并结合相邻正文解释。' },
  { icon: Sparkles, title: '对比信息', text: '请对比知识库中相互关联的规定，指出一致与冲突之处。' },
]

async function send(text: string) {
  if (!knowledge.activeId) return
  await chat.send(text, knowledge.activeId)
}

watch(
  () => chat.messages.map((message) => message.content).join('|'),
  async () => {
    await nextTick()
    list.value?.scrollTo({ top: list.value.scrollHeight, behavior: 'smooth' })
  },
)
</script>

<template>
  <section class="chat-view">
    <header class="chat-header">
      <div>
        <strong>{{ knowledge.active?.name || 'Company AI' }}</strong>
        <span v-if="knowledge.active">{{ knowledge.active.document_count }} 份文档</span>
      </div>
      <span class="private-badge">私有知识库</span>
    </header>

    <div ref="list" class="chat-scroll">
      <div v-if="!chat.messages.length" class="welcome-state">
        <div class="welcome-mark"><Sparkles :size="28" /></div>
        <h1>{{ ready ? `今天想了解什么？` : '先创建一个知识库' }}</h1>
        <p>
          {{
            ready
              ? `我会从「${knowledge.active?.name}」中检索文字、表格与图片语义，并附上可追溯来源。`
              : '前往知识库管理页创建空间并上传 Word、PDF、PPT、Markdown 或 TXT，然后就可以开始问答。'
          }}
        </p>
        <div v-if="ready" class="suggestion-grid">
          <button
            v-for="item in suggestions"
            :key="item.title"
            @click="composer?.setValue(item.text)"
          >
            <component :is="item.icon" :size="18" />
            <strong>{{ item.title }}</strong>
            <span>{{ item.text }}</span>
          </button>
        </div>
        <RouterLink v-else class="primary-button" to="/knowledge">去创建知识库</RouterLink>
      </div>

      <div v-else class="message-list">
        <ChatMessage v-for="message in chat.messages" :key="message.id" :message="message" />
      </div>
    </div>

    <PromptComposer
      ref="composer"
      :disabled="!ready || chat.sending"
      :placeholder="ready ? '向公司知识库提问' : '请先创建并选择知识库'"
      @send="send"
    />
  </section>
</template>
