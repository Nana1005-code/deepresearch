<template>
  <div class="paper-search-input">
    <input :value="modelValue" aria-label="搜索真实论文" role="combobox" aria-autocomplete="list" :aria-expanded="open && items.length>0" aria-controls="paper-suggestions" :aria-activedescendant="active>=0?'paper-suggestion-'+active:undefined" placeholder="搜索论文、中文主题、作者或期刊" maxlength="200" @input="change" @focus="focused=true;schedule()" @blur="focused=false;open=false" @keydown="key" />
    <div v-if="open && items.length" id="paper-suggestions" role="listbox" aria-label="真实论文搜索联想" class="paper-suggestions">
      <button v-for="(item,index) in items" :id="'paper-suggestion-'+index" :key="item.kind+item.id" type="button" role="option" :aria-selected="active===index" :class="{active:active===index}" @mousedown.prevent @click="choose(item)"><span>{{ item.label }}</span><small>{{ item.kind==='topic'?'主题 · '+item.count+' 篇论文':'已导入论文' }}</small></button>
    </div>
    <span v-if="failed" class="suggestion-error">联想加载失败，可直接点击搜索</span>
  </div>
</template>
<script setup lang="ts">
import {ref,onBeforeUnmount} from 'vue';
import {api} from '../../services/api';
const props=defineProps<{modelValue:string}>();
const emit=defineEmits<{'update:modelValue':[value:string];search:[]}>();
interface Suggestion{id:string;label:string;kind:'topic'|'paper';count?:number}
const items=ref<Suggestion[]>([]),open=ref(false),focused=ref(false),failed=ref(false),active=ref(-1);
let timer:ReturnType<typeof setTimeout>|undefined,version=0;
function change(event:Event){emit('update:modelValue',(event.target as HTMLInputElement).value);schedule();}
function schedule(){clearTimeout(timer);version++;items.value=[];active.value=-1;failed.value=false;timer=setTimeout(load,250);}
async function load(){const token=++version;const query=props.modelValue.trim();if(!query){open.value=false;return;}try{const result=await api<Suggestion[]>(`/research-square/openalex/work-suggestions?q=${encodeURIComponent(query)}`);if(token===version){items.value=result;open.value=focused.value;}}catch{if(token===version)failed.value=true;}}
function choose(item:Suggestion){version++;clearTimeout(timer);open.value=false;items.value=[];active.value=-1;emit('update:modelValue',item.label);emit('search');}
function key(event:KeyboardEvent){if(event.isComposing||event.keyCode===229)return;if(event.key==='Escape'){version++;open.value=false;active.value=-1;}else if(open.value&&items.value.length&&(event.key==='ArrowDown'||event.key==='ArrowUp')){event.preventDefault();active.value=(active.value+(event.key==='ArrowDown'?1:-1)+items.value.length)%items.value.length;}else if(event.key==='Enter'){if(open.value&&active.value>=0){event.preventDefault();choose(items.value[active.value]);}else{version++;clearTimeout(timer);open.value=false;}}}
onBeforeUnmount(()=>{version++;clearTimeout(timer);});
</script>
<style scoped>
.paper-search-input{position:relative;flex:1;min-width:180px}.paper-search-input input{box-sizing:border-box;width:100%;font:inherit;padding:9px;border:1px solid #d7deed;border-radius:8px;background:white;color:#27344e}.paper-suggestions{position:absolute;z-index:15;top:calc(100% + 5px);left:0;right:0;max-height:280px;overflow:auto;border:1px solid #d7deed;border-radius:10px;background:#fff;box-shadow:0 8px 24px #25364c24;padding:5px}.paper-suggestions button{display:flex;flex-direction:column;gap:4px;width:100%;padding:10px;text-align:left;background:white;border:0;border-radius:6px;color:#304b7c;cursor:pointer}.paper-suggestions button:hover,.paper-suggestions .active{background:#edf3ff}.paper-suggestions span{overflow-wrap:anywhere;font-size:13px}.paper-suggestions small{color:#8593aa;font-size:11px}.suggestion-error{font-size:11px;color:#a44648}
</style>
