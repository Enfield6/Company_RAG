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

type RichImageGroup = {
  id: string
  type: 'image-group'
  images: RichImageBlock[]
}

const imageState = reactive<Record<string, 'loading' | 'loaded' | 'error'>>({})
const imageRatio = reactive<Record<string, number>>({})
const imageCount = computed(() => props.blocks.filter((block) => block.type === 'image').length)
const renderBlocks = computed<Array<Exclude<RichBlock, RichImageBlock> | RichImageGroup>>(() => {
  const result: Array<Exclude<RichBlock, RichImageBlock> | RichImageGroup> = []
  for (const block of props.blocks) {
    if (block.type !== 'image') {
      result.push(block)
      continue
    }
    const previous = result.at(-1)
    if (previous?.type === 'image-group') {
      previous.images.push(block)
    } else {
      result.push({ id: `image-group-${block.id}`, type: 'image-group', images: [block] })
    }
  }
  return result
})

function imageStatus(id: string) {
  return imageState[id] || 'loading'
}

function handleImageLoad(id: string, event: Event) {
  const image = event.currentTarget as HTMLImageElement
  if (image.naturalWidth && image.naturalHeight) {
    imageRatio[id] = image.naturalWidth / image.naturalHeight
  }
  imageState[id] = 'loaded'
}

function imageStageStyle(id: string) {
  const ratio = imageRatio[id]
  if (!ratio) return undefined
  return { aspectRatio: String(Math.min(3.8, Math.max(1.1, ratio))) }
}
</script>

<template>
  <section class="rich-answer" :class="{ 'rich-answer--preview': preview }">
    <div v-if="!preview" class="rich-answer-kicker">
      <span><Sparkles :size="13" /> 知识库图文解答</span>
      <span v-if="imageCount"><GalleryHorizontalEnd :size="13" /> {{ imageCount }} 张相关配图</span>
      <span v-if="streaming" class="rich-live"><i />生成中</span>
    </div>

    <article class="rich-article">
      <template v-for="block in renderBlocks" :key="block.id">
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

        <section
          v-else-if="block.type === 'image-group'"
          class="rich-inline-media"
          aria-label="与当前回答段落相关的文档图片"
        >
          <header v-if="!preview" class="rich-inline-media-header">
            <span><ImageIcon :size="14" /> 操作界面参考</span>
            <small>对应上文内容 · {{ block.images.length }} 张</small>
          </header>
          <div
            class="rich-image-grid"
            :class="{ 'rich-image-grid--single': block.images.length === 1 }"
          >
            <figure v-for="image in block.images" :key="image.id" class="rich-image-card">
              <div
                class="rich-image-stage"
                :class="`rich-image-stage--${imageStatus(image.id)}`"
                :style="imageStageStyle(image.id)"
              >
                <div v-if="imageStatus(image.id) === 'loading'" class="image-loading">
                  <ImageIcon :size="24" />
                  <span>正在载入文档配图</span>
                </div>
                <div v-if="imageStatus(image.id) === 'error'" class="image-error">
                  <ImageIcon :size="24" />
                  <span>这张文档图片暂时无法显示</span>
                </div>
                <img
                  :src="documentImageUrl(image.document_id, image.sequence_no)"
                  :alt="image.alt"
                  loading="lazy"
                  @load="handleImageLoad(image.id, $event)"
                  @error="imageState[image.id] = 'error'"
                />
              </div>
              <figcaption>
                <p>{{ image.caption }}</p>
                <div>
                  <span><Link2 :size="12" />{{ image.source_label }}</span>
                  <span class="image-relation">
                    {{ image.relation === 'direct' ? '直接命中' : '相关界面' }}
                  </span>
                  <span v-if="image.source_rank">来源 {{ image.source_rank }}</span>
                </div>
              </figcaption>
            </figure>
          </div>
        </section>
      </template>
    </article>
  </section>
</template>
