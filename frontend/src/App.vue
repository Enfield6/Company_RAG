<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { Menu } from '@lucide/vue'
import AppSidebar from './components/AppSidebar.vue'
import { useChatStore } from './stores/chat'
import { useKnowledgeStore } from './stores/knowledge'

const knowledge = useKnowledgeStore()
const chat = useChatStore()
const sidebarOpen = ref(false)

onMounted(async () => {
  await knowledge.load()
  await chat.loadConversations(knowledge.activeId || undefined)
})

watch(
  () => knowledge.activeId,
  async (next, previous) => {
    if (next === previous) return
    chat.newChat()
    await chat.loadConversations(next || undefined)
  },
)
</script>

<template>
  <div class="app-shell">
    <AppSidebar :open="sidebarOpen" @close="sidebarOpen = false" />
    <div v-if="sidebarOpen" class="sidebar-scrim" @click="sidebarOpen = false" />
    <main class="main-shell">
      <button class="mobile-menu" aria-label="打开菜单" @click="sidebarOpen = true">
        <Menu :size="20" />
      </button>
      <RouterView />
    </main>
  </div>
</template>
