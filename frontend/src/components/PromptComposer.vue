<script setup lang="ts">
import { nextTick, ref } from 'vue'
import { ArrowUp, Paperclip } from '@lucide/vue'

const props = defineProps<{ disabled?: boolean; placeholder?: string }>()
const emit = defineEmits<{ send: [value: string] }>()
const value = ref('')
const textarea = ref<HTMLTextAreaElement>()

function resize() {
  if (!textarea.value) return
  textarea.value.style.height = 'auto'
  textarea.value.style.height = `${Math.min(textarea.value.scrollHeight, 180)}px`
}

function submit() {
  const text = value.value.trim()
  if (!text || props.disabled) return
  emit('send', text)
  value.value = ''
  void nextTick(resize)
}

function keydown(event: KeyboardEvent) {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    submit()
  }
}

function setValue(text: string) {
  value.value = text
  void nextTick(() => {
    resize()
    textarea.value?.focus()
  })
}

defineExpose({ setValue })
</script>

<template>
  <div class="composer-wrap">
    <div class="composer" :class="{ disabled }">
      <button class="composer-tool" type="button" aria-label="附件将在知识库页面上传" disabled>
        <Paperclip :size="19" />
      </button>
      <textarea
        ref="textarea"
        v-model="value"
        rows="1"
        :disabled="disabled"
        :placeholder="placeholder || '向公司知识库提问'"
        aria-label="输入问题"
        @input="resize"
        @keydown="keydown"
      />
      <button
        class="send-button"
        type="button"
        :disabled="disabled || !value.trim()"
        aria-label="发送"
        @click="submit"
      >
        <ArrowUp :size="19" />
      </button>
    </div>
    <p>回答可能存在偏差，请核对引用原文后再用于重要决策。</p>
  </div>
</template>
