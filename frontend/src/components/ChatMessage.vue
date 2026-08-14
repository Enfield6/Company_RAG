<script setup lang="ts">
import { ref } from 'vue'
import { Bot, ChevronDown, FileText, Image, LoaderCircle, UserRound } from '@lucide/vue'
import { documentImageUrl } from '../api/client'
import type { ChatMessage } from '../types'
import InlineRichText from './InlineRichText.vue'
import RichAnswer from './RichAnswer.vue'

defineProps<{ message: ChatMessage }>()
const citationsOpen = ref(false)
</script>

<template>
  <article class="message-row" :class="`message-row--${message.role}`">
    <div class="message-avatar">
      <UserRound v-if="message.role === 'user'" :size="18" />
      <Bot v-else :size="18" />
    </div>
    <div class="message-body">
      <div class="message-author">{{ message.role === 'user' ? '你' : 'Company AI' }}</div>
      <template v-if="message.role === 'assistant'">
        <div v-if="message.status_text && message.streaming" class="answer-status">
          <LoaderCircle :size="14" />
          <span>{{ message.status_text }}</span>
          <i /><i /><i />
        </div>
        <RichAnswer
          v-if="message.content_blocks?.length"
          :blocks="message.content_blocks"
          :streaming="message.streaming"
        />
        <template v-else>
          <div class="message-content" :class="{ 'message-error': message.error }">
            <InlineRichText :text="message.content" /><span
              v-if="message.streaming"
              class="typing-cursor"
            />
          </div>
          <RichAnswer
            v-if="message.media_blocks?.length"
            :blocks="message.media_blocks"
            preview
          />
        </template>
      </template>
      <div v-else class="message-content">{{ message.content }}</div>

      <div v-if="message.citations?.length" class="citations">
        <button class="citations-toggle" @click="citationsOpen = !citationsOpen">
          <FileText :size="15" />
          {{ message.citations.length }} 条参考来源
          <ChevronDown :size="15" :class="{ rotated: citationsOpen }" />
        </button>
        <div v-if="citationsOpen" class="citation-grid">
          <article v-for="citation in message.citations" :key="citation.chunk_id" class="citation-card">
            <div class="citation-meta">
              <span>来源 {{ citation.rank }}</span>
              <span>{{ Math.round(citation.score * 100) }}% 相关</span>
            </div>
            <p>{{ citation.quote }}</p>
            <img
              v-if="citation.chunk_type === 'image' && citation.sequence_no !== undefined"
              :src="documentImageUrl(citation.document_id, citation.sequence_no)"
              alt="文档引用图片"
              loading="lazy"
            />
            <span v-if="citation.chunk_type === 'image'" class="image-source">
              <Image :size="13" /> 图片内容
            </span>
          </article>
        </div>
      </div>
    </div>
  </article>
</template>
