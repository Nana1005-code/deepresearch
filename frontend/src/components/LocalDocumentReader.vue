<template>
  <div class="document-reader">
    <header class="reader-header">
      <div class="reader-brand"><span class="reader-logo" aria-hidden="true">▤</span><div><strong>文献文本</strong><small>深度研究助手</small></div></div>
      <span v-if="result" class="reader-badge">解析完成</span>
    </header>
    <main class="reader-main">
      <div v-if="pendingUpload" class="reader-state" role="status">
        <h1>正在导入文献…</h1><p>导入完成后会直接打开原文件，请保留原研究页面。</p>
      </div>
      <div v-else-if="loading" class="reader-state" role="status">正在读取文献文本…</div>
      <div v-else-if="error" class="reader-state reader-error" role="alert">
        <h1>暂时无法查看文本</h1><p>{{ error }}</p><button type="button" @click="loadText">重试</button>
      </div>
      <template v-else-if="result">
        <div class="reader-title"><span class="reader-type">{{ result.document.extension.replace('.', '').toUpperCase() }}</span><h1>{{ result.document.title }}</h1></div>
        <p class="reader-meta">{{ formatSize(result.document.size_bytes) }} · {{ result.document.chunk_count }} 个文本片段<span v-if="result.document.page_count"> · {{ result.document.page_count }} 页</span> · 本地文献</p>
        <article class="text-paper" aria-label="文献全文">
          <div class="paper-label">提取的文本内容</div>
          <div class="document-text">{{ result.text || '该文献没有可显示的文本。' }}</div>
        </article>
        <p class="reader-footnote">当前展示解析后的纯文本内容，原文件排版不保留。</p>
      </template>
    </main>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref } from "vue";
import { api } from "../services/api";

interface DocumentText {
  document: { title: string; extension: string; size_bytes: number; chunk_count: number; page_count: number | null };
  text: string;
}
const identifier = new URLSearchParams(window.location.search).get("documentPreview") || "";
const pendingUpload = identifier === "loading";
const loading = ref(!pendingUpload);
const error = ref("");
const result = ref<DocumentText | null>(null);
let controller: AbortController | undefined;

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

async function loadText() {
  if (pendingUpload) return;
  error.value = "";
  loading.value = true;
  controller = new AbortController();
  const timeout = window.setTimeout(() => controller?.abort(), 60000);
  try {
    if (!identifier) throw new Error("缺少文献编号，请从资料库重新打开。");
    result.value = await api<DocumentText>(`/documents/${encodeURIComponent(identifier)}/text`, { signal: controller.signal });
    document.title = `${result.value.document.title} - 文献文本`;
  } catch (cause) {
    error.value = cause instanceof Error && cause.name === "AbortError"
      ? "读取超时，请重试。"
      : cause instanceof Error ? cause.message : "文献文本读取失败";
  } finally {
    window.clearTimeout(timeout);
    loading.value = false;
  }
}
onMounted(() => {
  document.title = pendingUpload ? "正在导入文献…" : "文献文本";
  void loadText();
});
onUnmounted(() => controller?.abort());
</script>

<style scoped>
.document-reader { min-height: 100vh; background: #f2f5ff; color: #26334d; font-family: "Microsoft YaHei", "PingFang SC", sans-serif; }
.reader-header { background: #fff; border-bottom: 1px solid #dce4f7; padding: 18px max(24px, calc((100% - 1000px) / 2)); display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.reader-brand { display: flex; align-items: center; gap: 12px; }
.reader-brand strong { font-size: 16px; }
.reader-brand small { display: block; margin-top: 3px; font-size: 12px; color: #7183a2; }
.reader-logo { display: grid; place-items: center; width: 38px; height: 38px; border-radius: 11px; background: linear-gradient(135deg, #3374fa, #7843f1); color: #fff; font-size: 22px; }
.reader-badge { color: #087f75; background: #e5f7f1; border-radius: 5px; padding: 3px 8px; font-size: 12px; white-space: nowrap; }
.reader-main { max-width: 1000px; margin: auto; padding: 36px 24px; }
.reader-title { display: flex; align-items: center; gap: 12px; }
.reader-type { flex-shrink: 0; padding: 5px 8px; border-radius: 5px; background: #e5edff; color: #3b70ee; font-size: 12px; }
h1 { margin: 0; font-size: 22px; font-weight: 600; overflow-wrap: anywhere; min-width: 0; }
.reader-meta, .reader-footnote { color: #7183a2; font-size: 12px; }
.reader-meta { margin: 12px 0 24px; }
.text-paper { background: #fff; border: 1px solid #dce4f7; border-radius: 14px; padding: 28px 36px; }
.paper-label { color: #7183a2; font-size: 12px; padding-bottom: 16px; margin-bottom: 20px; border-bottom: 1px solid #e7ecf6; }
.document-text { white-space: pre-wrap; overflow-wrap: anywhere; font-size: 15px; line-height: 1.95; tab-size: 4; }
.reader-state { background: #fff; border: 1px solid #dce4f7; border-radius: 14px; padding: 28px; }
.reader-state p { color: #7183a2; }
.reader-error h1 { color: #a63f46; }
.reader-state button { border: 1px solid #cbdaf0; background: #fff; color: #3267ad; border-radius: 8px; padding: 8px 18px; cursor: pointer; }
@media (max-width: 520px) { .reader-header { padding: 16px; } .reader-main { padding: 24px 14px; } .text-paper { padding: 20px 18px; } h1 { font-size: 18px; } }
</style>
