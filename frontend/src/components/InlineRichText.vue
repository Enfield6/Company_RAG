<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ text: string }>()

type InlineSegment = {
  type: 'text' | 'source' | 'strong' | 'emphasis' | 'code' | 'strike'
  value: string
  rank?: string
}

type InlineRule = {
  type: Exclude<InlineSegment['type'], 'text'>
  pattern: RegExp
}

const inlineRules: InlineRule[] = [
  { type: 'source', pattern: /^\[来源(\d+)]/ },
  { type: 'code', pattern: /^`([^`\n]+)`/ },
  { type: 'strong', pattern: /^\*\*(?=\S)([^\n]*?\S)\*\*/ },
  { type: 'strong', pattern: /^__(?=\S)([^\n]*?\S)__/ },
  { type: 'strike', pattern: /^~~(?=\S)([^\n]*?\S)~~/ },
  { type: 'emphasis', pattern: /^\*(?!\*)(?=\S)([^*\n]*?\S)\*/ },
  { type: 'emphasis', pattern: /^_(?!_)(?=\S)([^_\n]*?\S)_/ },
]

function pushText(segments: InlineSegment[], value: string) {
  if (!value) return
  const previous = segments.at(-1)
  if (previous?.type === 'text') {
    previous.value += value
    return
  }
  segments.push({ type: 'text', value })
}

function parseInlineMarkdown(text: string): InlineSegment[] {
  const segments: InlineSegment[] = []
  let cursor = 0

  while (cursor < text.length) {
    const remaining = text.slice(cursor)
    const matchedRule = inlineRules
      .map((rule) => ({ rule, match: remaining.match(rule.pattern) }))
      .find((candidate) => candidate.match)

    if (!matchedRule?.match) {
      pushText(segments, text[cursor])
      cursor += 1
      continue
    }

    const [raw, value] = matchedRule.match
    segments.push({
      type: matchedRule.rule.type,
      value,
      rank: matchedRule.rule.type === 'source' ? value : undefined,
    })
    cursor += raw.length
  }

  return segments
}

const segments = computed(() => parseInlineMarkdown(props.text))
</script>

<template>
  <template v-for="(segment, index) in segments" :key="`${segment.value}-${index}`">
    <span v-if="segment.type === 'source'" class="inline-source">{{ segment.rank }}</span>
    <strong v-else-if="segment.type === 'strong'">{{ segment.value }}</strong>
    <em v-else-if="segment.type === 'emphasis'">{{ segment.value }}</em>
    <code v-else-if="segment.type === 'code'" class="inline-code">{{ segment.value }}</code>
    <s v-else-if="segment.type === 'strike'">{{ segment.value }}</s>
    <template v-else>{{ segment.value }}</template>
  </template>
</template>
