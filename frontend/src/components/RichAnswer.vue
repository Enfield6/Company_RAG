<script setup lang="ts">
import { computed, reactive } from 'vue'
import { GalleryHorizontalEnd, Image as ImageIcon, Link2, Sparkles } from '@lucide/vue'
import { documentImageUrl } from '../api/client'
import type { RichBlock, RichImageBlock } from '../types'
import InlineRichText from './InlineRichText.vue'

const props = withDefaults(
  defineProps<{
    blocks: RichBlock[]
    streaming?: boolean
    preview?: boolean
  }>(),
  { streaming: false, preview: false },
)

const imageState = reactive<Record<string, 'loading' | 'loaded' | 'error'>>({})
const imageCount = computed(() => props.blocks.filter((block) => block.type === 'image').length)

function imageBlock(block: RichBlock): RichImageBlock {
  return block as RichImageBlock
}

function imageStatus(id: string) {
  return imageState[id] || 'loading'
}
</script>

<template>
  <section class="rich-answer" :class="{ 'rich-answer--preview': preview }">
    <div v-if="!preview" class="rich-answer-kicker">
      <span><Sparkles :size="13" /> 知识库图文解答</span>
      <span v-if="imageCount"><GalleryHorizontalEnd :size="13" /> {{ imageCount }} 张相关配图</span>
      <span v-if="streaming" class="rich-live"><i />生成中</span>
    </div>

    <template v-for="block in blocks" :key="block.id">
      <h2
        v-if="block.type === 'heading'"
        class="rich-heading"
        :class="`rich-heading--${block.level || 2}`"
      >
        <InlineRichText :text="block.text" />
      </h2>

      <p v-else-if="block.type === 'lead'" class="rich-lead">
        <InlineRichText :text="block.text" />
      </p>

      <p v-else-if="block.type === 'paragraph'" class="rich-paragraph">
        <InlineRichText :text="block.text" />
      </p>

      <aside v-else-if="block.type === 'callout'" class="rich-callout">
        <span><Sparkles :size="16" /></span>
        <p><InlineRichText :text="block.text" /></p>
      </aside>

      <ol
        v-else-if="block.type === 'list'"
        class="rich-list"
        :class="{ 'rich-list--bullet': block.style === 'bullet' }"
      >
        <li v-for="(item, index) in block.items" :key="`${block.id}-${index}`">
          <span>{{ block.style === 'ordered' ? index + 1 : '•' }}</span>
          <p><InlineRichText :text="item" /></p>
        </li>
      </ol>

      <figure v-else-if="block.type === 'image'" class="rich-image-card">
        <div class="rich-image-stage" :class="`rich-image-stage--${imageStatus(block.id)}`">
          <div v-if="imageStatus(block.id) === 'loading'" class="image-loading">
            <ImageIcon :size="24" />
            <span>正在载入文档配图</span>
          </div>
          <div v-if="imageStatus(block.id) === 'error'" class="image-error">
            <ImageIcon :size="24" />
            <span>这张文档图片暂时无法显示</span>
          </div>
          <img
            :src="documentImageUrl(imageBlock(block).document_id, imageBlock(block).sequence_no)"
            :alt="imageBlock(block).alt"
            loading="lazy"
            @load="imageState[block.id] = 'loaded'"
            @error="imageState[block.id] = 'error'"
          />
        </div>
        <figcaption>
          <p>{{ imageBlock(block).caption }}</p>
          <div>
            <span><Link2 :size="12" />{{ imageBlock(block).source_label }}</span>
            <span class="image-relation">
              {{ imageBlock(block).relation === 'direct' ? '直接命中' : '相关文档配图' }}
            </span>
            <span v-if="imageBlock(block).source_rank">来源 {{ imageBlock(block).source_rank }}</span>
          </div>
        </figcaption>
      </figure>
    </template>
  </section>
</template>
