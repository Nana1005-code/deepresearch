<template>
  <div class="graph-explorer">
    <button v-if="dataSource==='openalex'" type="button" class="collection-entry" @click="openCollection">LLM 知识库 · 研究方向总览</button><p v-if="collection" class="focus-label">按已导入论文标题和摘要整理的专题节点；连线表示论文共现，不代表 OpenAlex 官方上下级分类。点击节点查看证据论文。</p>
    <form class="node-search" @submit.prevent="search">
      <input v-model="query" aria-label="搜索图谱节点" placeholder="搜索节点，如：多模态" @input="schedule" @keydown.esc="results=[]" />
      <button type="submit">搜索节点</button><button v-if="focused" type="button" @click="reset">返回完整图谱</button>
    </form>
    <div v-if="results.length" class="node-results" aria-label="节点联想结果"><button v-for="item in results" :key="item.public_id" @click="focus(item)">{{ item.name }} <small>{{ item.research_count }} {{ dataSource==='local'?'条研究':'篇论文' }}</small></button></div>
    <p v-if="busy" role="status">正在查询…</p><p v-if="error" role="alert">{{ error }}</p>
    <p v-if="searched && !busy && !results.length && !focused">没有匹配的已存节点，请尝试其他关键词。</p>
    <p v-if="focused" class="focus-label">{{ focused }} · 关联节点视图（全部已导入数据）<span v-if="!view.edges.length"> · 暂无关联节点</span></p>
    <details v-if="focused && view.nodes.some(node=>node.id.startsWith('concept-'))" class="direction-directory" open><summary>相关研究方向 · 点击查看论文</summary><div><button v-for="node in view.nodes.filter(node=>node.id.startsWith('concept-'))" :key="node.id" type="button" @click="$emit('select',node)">{{ node.name }} <small>{{ node.research_count }} 篇</small></button></div></details>
    <TopicGraph :data="focused?view:data" :period-days="365" :data-source="dataSource" @select="$emit('select',$event)" />
  </div>
</template>
<script setup lang="ts">
import {ref,watch,onBeforeUnmount} from 'vue';
import {api} from '../../services/api';
import TopicGraph,{type TopicGraphData,type TopicGraphNode} from './TopicGraph.vue';
const props=defineProps<{data:TopicGraphData;dataSource:'local'|'openalex'}>();
defineEmits<{select:[node:TopicGraphNode]}>();
interface Match{public_id:string;name:string;research_count:number}
const collection=ref(false);
const query=ref(''),focused=ref(''),results=ref<Match[]>([]),view=ref<TopicGraphData>({nodes:[],edges:[]}),busy=ref(false),error=ref(''),searched=ref(false);
let version=0,timer:ReturnType<typeof setTimeout>|undefined;
function schedule(){version++;clearTimeout(timer);timer=setTimeout(search,250);}
async function search(){clearTimeout(timer);const token=++version;results.value=[];error.value='';searched.value=!!query.value.trim();if(!searched.value){busy.value=false;return;}busy.value=true;try{const items=await api<Match[]>(`/research-square/nodes/search?source=${props.dataSource}&q=${encodeURIComponent(query.value.trim())}`);if(token===version)results.value=items;}catch{if(token===version)error.value='节点搜索失败，请重试';}finally{if(token===version)busy.value=false;}}
async function openCollection(){const token=++version;busy.value=true;error.value='';try{const result=await api<TopicGraphData>('/research-square/concepts/llm-graph');if(token===version){view.value=result;focused.value='LLM 知识库';collection.value=true;results.value=[];searched.value=false;}}catch{error.value='专题加载失败，请重试';}finally{if(token===version)busy.value=false;}}
async function focus(item:Match){collection.value=false;clearTimeout(timer);const token=++version;busy.value=true;error.value='';try{const graph=await api<TopicGraphData>(`/research-square/nodes/${item.public_id}/graph?source=${props.dataSource}`);if(token===version){view.value=graph;focused.value=item.name;results.value=[];searched.value=false;}}catch{if(token===version)error.value='关联图谱加载失败，请重试';}finally{if(token===version)busy.value=false;}}
function reset(){collection.value=false;version++;clearTimeout(timer);focused.value='';query.value='';results.value=[];searched.value=false;busy.value=false;error.value='';}
watch(()=>props.dataSource,reset);onBeforeUnmount(()=>{version++;clearTimeout(timer);});
</script>
<style scoped>
.node-search{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0}.node-search input{flex:1;min-width:140px;border:1px solid #d7deed;border-radius:9px;padding:10px;font:inherit}.node-search button,.node-results button{border:1px solid #d7deed;border-radius:9px;background:#f5f8ff;padding:10px 14px;color:#365ac0;cursor:pointer}.node-results{display:flex;flex-wrap:wrap;gap:8px;max-height:220px;overflow:auto;margin-bottom:12px}.node-results small{color:#7e8ba1}.focus-label{font-size:13px;color:#526991}
.collection-entry{padding:10px 14px;border:1px solid #b5c7f5;border-radius:9px;background:#edf3ff;color:#365ac0;cursor:pointer;font-weight:600;margin-top:12px}
.direction-directory{margin:12px 0;padding:12px;background:#f6f8fe;border-radius:10px;color:#526991;font-size:12px}.direction-directory summary{cursor:pointer;font-weight:600}.direction-directory>div{display:flex;flex-wrap:wrap;gap:7px;margin-top:10px}.direction-directory button{border:1px solid #dbe3f4;border-radius:7px;background:#fff;color:#365ac0;padding:6px 9px;cursor:pointer}.direction-directory small{color:#8a97ab}
</style>
