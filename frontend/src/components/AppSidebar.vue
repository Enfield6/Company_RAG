<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  BookOpen,
  Bot,
  ChevronDown,
  Database,
  MessageSquare,
  PanelLeftClose,
  Plus,
  ShieldCheck,
} from '@lucide/vue'
import { useChatStore } from '../stores/chat'
import { useKnowledgeStore } from '../stores/knowledge'

defineProps<{ open: boolean }>()
const emit = defineEmits<{ close: [] }>()
const route = useRoute()
const router = useRouter()
const knowledge = useKnowledgeStore()
const chat = useChatStore()
const currentTitle = computed(() => knowledge.active?.name || '选择知识库')

function startChat() {
  chat.newChat()
  void router.push('/')
  emit('close')
}

async function openConversation(id: string) {
  await chat.openConversation(id)
  await router.push('/')
  emit('close')
}
</script>

<template>
  <aside class="sidebar" :class="{ 'sidebar--open': open }">
    <div class="sidebar-brand">
      <span class="brand-mark"><Bot :size="20" /></span>
      <div>
        <strong>Company AI</strong>
        <span>企业知识助手</span>
      </div>
      <button class="icon-button sidebar-close" aria-label="关闭菜单" @click="emit('close')">
        <PanelLeftClose :size="18" />
      </button>
    </div>

    <button class="new-chat" @click="startChat">
      <Plus :size="18" />
      <span>新建对话</span>
    </button>

    <label class="kb-picker">
      <span>当前知识库</span>
      <div class="kb-select-wrap">
        <Database :size="16" />
        <select
          :value="knowledge.activeId"
          aria-label="选择知识库"
          @change="knowledge.setActive(($event.target as HTMLSelectElement).value)"
        >
          <option v-if="!knowledge.items.length" value="">尚未创建</option>
          <option v-for="item in knowledge.items" :key="item.id" :value="item.id">
            {{ item.name }}
          </option>
        </select>
        <ChevronDown :size="15" />
      </div>
    </label>

    <nav class="primary-nav" aria-label="主导航">
      <RouterLink to="/" :class="{ active: route.name === 'chat' }" @click="emit('close')">
        <MessageSquare :size="17" />
        问答
      </RouterLink>
      <RouterLink
        to="/knowledge"
        :class="{ active: route.name === 'knowledge' }"
        @click="emit('close')"
      >
        <BookOpen :size="17" />
        知识库管理
      </RouterLink>
    </nav>

    <div class="history-section">
      <p class="section-label">最近对话</p>
      <button
        v-for="item in chat.conversations"
        :key="item.id"
        class="history-item"
        :class="{ active: chat.conversationId === item.id }"
        @click="openConversation(item.id)"
      >
        <MessageSquare :size="15" />
        <span>{{ item.title }}</span>
      </button>
      <p v-if="!chat.conversations.length" class="empty-history">还没有对话记录</p>
    </div>

    <div class="sidebar-footer">
      <ShieldCheck :size="16" />
      <div>
        <strong>{{ currentTitle }}</strong>
        <span>数据保留在私有环境</span>
      </div>
    </div>
  </aside>
</template>
