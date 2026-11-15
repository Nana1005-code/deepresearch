<template>
  <section class="topic-detail-page">
    <button class="back-button" type="button" @click="$emit('back')">← 返回知识图谱</button>
    <p v-if="error" class="error">{{ error }}</p>
    <div v-if="loading && !detail" class="loading">正在加载主题论文…</div>
    <template v-else-if="detail">
      <header class="topic-hero">
        <div><span v-if="publicId.startsWith('concept-')" class="eyebrow">论文证据专题</span><h1>{{ detail.name }}</h1>
          <p class="english-name">{{ detail.original_name }}</p><p>{{ detail.summary_zh||'暂无中文主题说明。' }}</p></div>
        <div class="hero-stats"><strong>{{ detail.stats.works }}</strong><span>相关论文</span><strong>{{ detail.stats.citations }}</strong><span>累计引用</span><template v-if="!publicId.startsWith('concept-')"><strong>{{ detail.stats.source_topics }}</strong><span>合并的OpenAlex主题</span></template></div>
      </header>
      <div v-if="!publicId.startsWith('concept-')" class="metadata-grid">
        <article><h2>领域归属</h2><div class="pills"><span v-for="item in detail.domains" :key="item.slug">{{ item.name }} {{ Math.round(item.relevance*100) }}%</span></div></article>
        <article><h2>规范名与别名</h2><div class="pills"><span v-for="alias in detail.aliases" :key="alias">{{ alias }}</span></div></article>
      </div>
      <article class="papers-card"><header><div><h2>相关论文</h2><p>搜索当前主题下的全部已导入论文，每页 5 篇。</p></div><b>{{ detail.total }} 篇</b></header>
        <form class="paper-filters" @submit.prevent="search"><input v-model="query" aria-label="搜索主题论文" placeholder="搜索标题、摘要、作者或期刊"/><button>搜索</button><select v-model="sort" aria-label="主题论文排序" @change="search"><option value="citations">引用量降序</option><option value="citations_asc">引用量升序</option><option value="latest">时间降序</option><option value="oldest">时间升序</option></select></form>
        <ol class="paper-list" :style="{'counter-reset':`paper ${(page-1)*5}`}">
          <li v-for="paper in detail.works" :key="paper.openalex_id">
            <span class="paper-rank"></span><div class="paper-main"><div class="paper-title-row"><h3>{{ paper.title }}</h3><strong>引用 {{ paper.cited_by_count }}</strong></div>
              <p class="paper-abstract">{{ paper.abstract||'暂无摘要' }}</p>
              <div class="paper-meta"><span>{{ paper.authors.slice(0,5).map(x=>x.name).join('、')||'作者未知' }}</span><span>{{ paper.source_name||'来源未知' }}</span><span>{{ paper.publication_date||'日期未知' }}</span><span v-if="!publicId.startsWith('concept-')">主题置信度 {{ Math.round((paper.topic_score||0)*100) }}%</span><span>{{ paper.is_oa?'开放获取':'非开放获取' }}</span></div>
              <a v-if="paper.landing_page_url||paper.oa_url" :href="paper.oa_url||paper.landing_page_url" target="_blank" rel="noopener">查看论文来源 ↗</a>
            </div>
          </li>
        </ol><nav v-if="detail.total>5" class="pagination"><button :disabled="page===1 || loading" @click="goPage(page-1)">上一页</button><span>第 {{ page }} / {{ Math.ceil(detail.total/5) }} 页</span><button :disabled="page*5>=detail.total || loading" @click="goPage(page+1)">下一页</button></nav><p v-if="!detail.works.length" class="empty">当前导入数据中没有该主题的论文。</p>
      </article>
    </template>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue';
import { api } from '../../services/api';

interface Paper {openalex_id:string;title:string;abstract?:string;publication_date?:string;source_name?:string;landing_page_url?:string;oa_url?:string;cited_by_count:number;is_oa:boolean;topic_score:number;authors:Array<{id?:string;name:string}>}
interface Detail {total:number;public_id:string;name:string;original_name?:string;summary_zh?:string;aliases:string[];domains:Array<{slug:string;name:string;relevance:number}>;stats:{works:number;citations:number;source_topics:number};works:Paper[];limit:number}
const props=defineProps<{publicId:string}>();defineEmits<{back:[]}>();
const query=ref(''),sort=ref('citations'),page=ref(1);let requestVersion=0;const detail=ref<Detail>();const loading=ref(false);const error=ref('');
async function load(){const version=++requestVersion;loading.value=true;error.value='';try{const result=await api<Detail>(`/research-square/${props.publicId.startsWith('concept-')?'concepts':'openalex/topics'}/${encodeURIComponent(props.publicId)}?limit=5&offset=${(page.value-1)*5}&q=${encodeURIComponent(query.value)}&sort=${sort.value}`);if(version===requestVersion)detail.value=result;}catch(e){if(version===requestVersion)error.value=e instanceof Error?e.message:'主题详情加载失败';}finally{if(version===requestVersion)loading.value=false;}}
function search(){page.value=1;void load();}function goPage(value:number){page.value=value;void load();}
onMounted(load);watch(()=>props.publicId,()=>{query.value='';sort.value='citations';page.value=1;void load();});
</script>

<style scoped>
.topic-detail-page{grid-column:2/4;align-self:stretch;overflow:auto;padding:28px 30px 60px;color:#27344e}.back-button{border:1px solid #cfd8eb;border-radius:10px;background:#fff;color:#4861b2;padding:9px 14px;font-weight:700;cursor:pointer;margin-bottom:15px}.topic-hero{display:grid;grid-template-columns:1fr auto;gap:28px;background:linear-gradient(135deg,#243c7d,#6b54d9);color:#fff;border-radius:22px;padding:28px 32px}.topic-hero h1{font-size:30px;margin:5px 0}.topic-hero p{max-width:850px;color:#e6eaff;line-height:1.65}.eyebrow{font-size:10px;letter-spacing:.16em;color:#cdd6ff}.english-name{font-weight:700}.hero-stats{display:grid;grid-template-columns:auto auto;gap:4px 12px;align-content:center;min-width:190px}.hero-stats strong{font-size:24px;text-align:right}.hero-stats span{align-self:center;color:#dbe2ff;font-size:12px}.metadata-grid{display:grid;grid-template-columns:.7fr 1.3fr;gap:14px;margin:14px 0}.metadata-grid article,.papers-card{background:#fff;border:1px solid #dfe6f2;border-radius:17px;padding:19px;box-shadow:0 8px 25px #2f477010}.metadata-grid h2,.papers-card h2{font-size:17px;margin:0 0 10px}.pills{display:flex;gap:7px;flex-wrap:wrap}.pills span{border-radius:20px;background:#edf2ff;color:#4964bf;padding:5px 9px;font-size:11px}.papers-card>header{display:flex;justify-content:space-between}.papers-card header p{color:#8491a9;font-size:11px}.papers-card header b{color:#4c65c5}.paper-list{counter-reset:paper;list-style:none;padding:0;margin:0;display:flex;flex-direction:column;gap:11px}.paper-list li{counter-increment:paper;display:grid;grid-template-columns:38px 1fr;border:1px solid #e3e8f2;background:#fbfcff;border-radius:13px;padding:14px}.paper-rank::before{content:counter(paper);display:flex;width:28px;height:28px;align-items:center;justify-content:center;border-radius:50%;background:#edf2ff;color:#506ac9;font-weight:700}.paper-title-row{display:flex;justify-content:space-between;gap:18px}.paper-title-row h3{margin:2px 0;font-size:15px}.paper-title-row strong{white-space:nowrap;color:#dd6844}.paper-abstract{font-size:12px;color:#5e6d84;line-height:1.55;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}.paper-meta{display:flex;flex-wrap:wrap;gap:5px 14px;color:#8491a9;font-size:10px}.paper-main a{display:inline-block;margin-top:8px;color:#4965ca;text-decoration:none;font-size:11px;font-weight:700}.loading,.empty{text-align:center;color:#8491a9;padding:80px}.error{background:#fff0f1;color:#b93144;padding:12px;border-radius:9px}@media(max-width:900px){.topic-detail-page{grid-column:1/-1;padding:16px}.topic-hero,.metadata-grid{grid-template-columns:1fr}.hero-stats{grid-template-columns:auto 1fr}.paper-title-row{display:block}}
.paper-main,.paper-title-row h3,.topic-hero>div{min-width:0}.paper-title-row h3{overflow-wrap:anywhere}.paper-title-row strong{flex-shrink:0;white-space:nowrap}.hero-stats strong,.hero-stats span{white-space:nowrap}.paper-filters,.pagination{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin:14px 0}.paper-filters input{flex:1;min-width:140px}.paper-filters input,.paper-filters select,.paper-filters button,.pagination button{padding:9px;border:1px solid #d7deed;border-radius:8px;background:#fff;color:#365ac0}.pagination{justify-content:center}.pagination button:disabled{opacity:.5}
</style>
