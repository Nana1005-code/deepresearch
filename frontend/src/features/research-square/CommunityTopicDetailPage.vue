<template>
  <section class="detail-page">
    <button class="back" type="button" @click="$emit('back')">← 返回用户研究图谱</button>
    <p v-if="error" class="error">{{ error }}</p>
    <div v-if="loading" class="loading">正在加载相关研究题目…</div>
    <template v-else-if="detail">
      <header class="hero">
        <div><h1>{{ detail.name }}</h1>
          <p>{{ detail.description }}</p></div>
        <div class="stats"><strong>{{ detail.stats.researches }}</strong><span>相关题目</span><strong>{{ detail.stats.user_researches }}</strong><span>我的研究</span><strong>{{ detail.stats.sample_researches }}</strong><span>样例数据</span></div>
      </header>
      <div class="metadata">
        <article><h2>概念类型</h2><span class="pill">{{ typeLabel(detail.concept_type) }}</span></article>
        <article><h2>规范名、别名与领域</h2><div class="pills"><span>{{ detail.name }}</span><span v-for="alias in detail.aliases" :key="alias">{{ alias }}</span><span v-for="domain in detail.domains" :key="domain.slug">{{ domain.name }}</span></div></article>
      </div>
      <article class="inputs-card"><header><div><h2>最新的完整研究输入</h2></div><b>{{ detail.researches.length }} 条</b></header>
        <ol class="input-list">
          <li v-for="item in detail.researches" :key="item.public_id">
            <span class="rank"></span><div><div class="input-meta"><span :class="['origin',item.data_origin]">{{ item.data_origin==='sample'?'样例':'我的研究' }}</span><time>{{ formatDate(item.published_at) }}</time></div><button v-if="item.data_origin==='user'" type="button" class="history-link" title="打开对应研究历史" @click="openHistory(item.source_run_id)">{{ item.research_input }}</button><p v-else>{{ item.research_input }}</p></div>
          </li>
        </ol>
        <p v-if="!detail.researches.length" class="empty">该关键词暂时没有关联的导入记录。</p>
      </article>
    </template>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue';
import { api } from '../../services/api';

interface ResearchInput {public_id:string;source_run_id:string;research_input:string;published_at:string;data_origin:'user'|'sample';extraction_status:string;heat_score:number;author:string}
interface Detail {description:string;public_id:string;name:string;concept_type:string;aliases:string[];domains:Array<{slug:string;name:string;relevance:number}>;stats:{researches:number;user_researches:number;sample_researches:number;heat:number};researches:ResearchInput[];limit:number}
const props=defineProps<{publicId:string}>();defineEmits<{back:[]}>();
const detail=ref<Detail>();const loading=ref(false);const error=ref('');
const labels:Record<string,string>={domain:'研究领域',task:'研究任务',method:'方法',modality:'数据模态',object:'研究对象',dataset:'数据集',metric:'评价指标',constraint:'约束',population:'研究人群',application:'应用场景',model:'模型',problem:'问题',topic:'研究概念'};
function typeLabel(value:string){return labels[value]||value||'研究概念';}
function formatDate(value:string){return new Date(value).toLocaleString('zh-CN');}
function openHistory(sourceRunId:string){if(!sourceRunId)return;window.history.pushState(null,'',`#research/${sourceRunId}`);window.dispatchEvent(new PopStateEvent('popstate'));}
async function load(){loading.value=true;error.value='';try{detail.value=await api<Detail>(`/research-square/community/topics/${encodeURIComponent(props.publicId)}?limit=100`);}catch(e){error.value=e instanceof Error?e.message:'关键词详情加载失败';}finally{loading.value=false;}}
onMounted(load);watch(()=>props.publicId,load);
</script>

<style scoped>
.detail-page{grid-column:2/4;align-self:stretch;overflow:auto;padding:28px 30px 60px;color:#27344e}.back{border:1px solid #cfd8eb;border-radius:10px;background:#fff;color:#4861b2;padding:9px 14px;font-weight:700;cursor:pointer;margin-bottom:15px}.hero{display:grid;grid-template-columns:1fr auto;gap:28px;background:linear-gradient(135deg,#244779,#5b63d9);color:#fff;border-radius:22px;padding:28px 32px}.hero h1{font-size:30px;margin:5px 0}.hero p{color:#e6eaff;line-height:1.65}.eyebrow{font-size:10px;letter-spacing:.16em;color:#cdd6ff}.stats{display:grid;grid-template-columns:auto auto;gap:4px 12px;align-content:center;min-width:190px}.stats strong{font-size:23px;text-align:right}.stats span{align-self:center;color:#dbe2ff;font-size:12px}.metadata{display:grid;grid-template-columns:.4fr 1.6fr;gap:14px;margin:14px 0}.metadata article,.inputs-card{background:#fff;border:1px solid #dfe6f2;border-radius:17px;padding:19px;box-shadow:0 8px 25px #2f477010}.metadata h2,.inputs-card h2{font-size:17px;margin:0 0 10px}.pill,.pills span{display:inline-block;border-radius:20px;background:#edf2ff;color:#4964bf;padding:5px 9px;font-size:11px}.pills{display:flex;gap:7px;flex-wrap:wrap}.inputs-card>header{display:flex;justify-content:space-between;gap:20px}.inputs-card header p{color:#8491a9;font-size:11px}.inputs-card header b{color:#4c65c5}.input-list{counter-reset:item;list-style:none;padding:0;margin:0;display:flex;flex-direction:column;gap:11px}.input-list li{counter-increment:item;display:grid;grid-template-columns:38px 1fr;border:1px solid #e3e8f2;background:#fbfcff;border-radius:13px;padding:15px}.rank::before{content:counter(item);display:flex;width:28px;height:28px;align-items:center;justify-content:center;border-radius:50%;background:#edf2ff;color:#506ac9;font-weight:700}.input-list p{font-size:14px;line-height:1.75;margin:10px 0 2px;white-space:pre-wrap}.input-meta{display:flex;gap:10px;align-items:center;color:#8491a9;font-size:11px}.origin{border-radius:12px;padding:3px 8px}.origin.user{background:#e8f7ef;color:#28724b}.origin.sample{background:#fff2dc;color:#9a6413}.loading,.empty{text-align:center;color:#8491a9;padding:80px}.error{background:#fff0f1;color:#b93144;padding:12px;border-radius:9px}@media(max-width:900px){.detail-page{grid-column:1/-1;padding:16px}.hero,.metadata{grid-template-columns:1fr}.stats{grid-template-columns:auto 1fr}}
.history-link{display:block;border:0;padding:0;background:transparent;color:#27344e;text-align:left;cursor:pointer;font-size:14px;line-height:1.75;margin:10px 0 2px;font-weight:650}.history-link:hover{color:#4965ca;text-decoration:underline}.history-link::after{content:'  打开研究历史 ↗';font-size:10px;color:#6d82cf}
</style>
