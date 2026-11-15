<template>
  <article class="gap-assistant" :aria-label="assistantName" @keydown.esc="historyOpen=false">
    <header class="gap-header">
      <div><h2>{{ assistantName }}</h2><small v-if="!academic">对照真实学术图谱，寻找我未研究或关注较少的相关主题</small></div>
      <div class="header-actions">
        <button type="button" :aria-label="''+shortName+'历史对话'" title="历史对话" :aria-expanded="historyOpen" :class="{selected:historyOpen}" @click="toggleHistory"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 6v6l4 3" stroke-linecap="round" stroke-linejoin="round"/></svg></button>
        <button type="button" :aria-label="'新建'+shortName+'对话'" title="新建对话" :disabled="busy || initializing" @click="newConversation">＋</button>
      </div>
    </header>
    <p v-if="academic" class="assistant-note">输入主题、趋势或关联问题，查询已导入的真实学术论文。</p>
    <section v-if="academic && !initializing && !conversation?.messages.length" class="academic-examples" aria-label="示例问题"><b>示例问题</b><div><button v-for="example in examples" :key="example" type="button" :disabled="busy || initializing" @click="question=example">{{ example }}</button></div></section>
    <div v-if="conversation?.messages.length" class="conversation-title" :title="conversation.title"><svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round" aria-hidden="true"><path d="M3 5h6l2 2h10v13H3z"/><path d="M3 10h18"/></svg><span>{{ conversation.title }}</span></div>

    <div v-if="historyOpen" class="history-backdrop" @click="historyOpen=false"></div>
    <section v-if="historyOpen" class="chat-history" role="dialog" :aria-label="''+shortName+'历史对话列表'">
      <header><h4>全部对话</h4><button type="button" :aria-label="'关闭'+shortName+'历史列表'" @click="historyOpen=false">×</button></header>

      <input v-model="historyQuery" type="search" :aria-label="'搜索'+shortName+'对话'" placeholder="搜索全部对话…" />
      <div class="conversation-list">
        <p v-if="!filteredHistory.length" class="history-empty">{{ historyQuery?'没有匹配的对话':'暂无历史对话' }}</p>
        <template v-for="(item,index) in filteredHistory" :key="item.id">
          <p v-if="index===0 || dateLabel(item.updated_at)!==dateLabel(filteredHistory[index-1].updated_at)" class="history-date">{{ dateLabel(item.updated_at) }}</p>
          <div class="history-item"><button type="button" class="conversation-row" :class="{active:item.id===conversation?.id}" :disabled="busy || initializing" @click="openConversation(item.id)"><strong>{{ item.title }}</strong><time>{{ timeLabel(item.updated_at) }}</time><span>{{ item.preview || '尚无消息' }}</span><small>{{ item.message_count }} 条消息{{ item.status==='running'?' · 分析中':'' }}</small></button><button type="button" class="delete-conversation" :disabled="busy || item.status==='running'" :aria-label="'删除'+shortName+'对话：'+item.title" title="删除对话" @click="askDelete(item)">×</button></div>
        </template>
      </div>
      <p v-if="historyError" class="error" role="alert">{{ historyError }} <button type="button" @click="loadHistory">重试</button></p>
    </section>
    <div v-if="deleteTarget" class="delete-overlay" @keydown.esc.stop="!deleting && (deleteTarget=null)">
      <section class="delete-dialog" role="alertdialog" aria-modal="true" aria-labelledby="gap-delete-title" @keydown.tab.prevent="focusDeleteAction">
        <h4 id="gap-delete-title">确定删除这条对话？</h4><p>“{{ deleteTarget.title }}”及其消息将被删除，无法恢复。</p><p v-if="deleteError" class="error" role="alert">{{ deleteError }}</p>
        <div><button ref="cancelDeleteButton" type="button" class="cancel-delete" :disabled="deleting" @click="deleteTarget=null">取消</button><button ref="confirmDeleteButton" type="button" class="confirm-delete" :disabled="deleting" @click="deleteConversation">{{ deleting?'正在删除…':'确认删除' }}</button></div>
      </section>
    </div>

    <div ref="messageList" class="gap-messages" aria-live="polite" :aria-label="''+shortName+'消息'">
      <p v-if="initializing" class="empty">正在载入对话…</p>
      <p v-else-if="!conversation?.messages.length" class="empty">{{ academic?'例如：最近一年真实论文数量最多的研究主题有哪些？':'例如：从我的研究历史来看，多模态学习还有哪些相关主题是我遗漏的？' }}</p>
      <div v-for="(message,index) in conversation?.messages || []" :key="index" class="message" :class="message.role">
        <p v-if="message.role==='user'" class="user-content">{{ message.content }}</p>
        <template v-else>
          <b class="assistant-label">研究助手</b>
          <template v-if="message.suggestions?.length">
            <p>建议补充了解以下主题：</p>
            <section v-for="(item,itemIndex) in message.suggestions" :key="itemIndex" class="gap-suggestion">
              <h3><button v-if="item.public_id" class="topic-link" @click="emit('topic',item.public_id)">{{ itemIndex+1 }}. {{ item.name }} ↗</button><span v-else>{{ itemIndex+1 }}. {{ item.name }}</span></h3>
              <p>与目标主题共同出现在 {{ item.cooccurrence_count }} 篇已导入论文中；我的相关研究记录 {{ item.my_research_count }} 条。</p>
            </section>
            <details class="analysis-details"><summary>查看研究助手分析</summary><ChatMarkdown :content="renderContent(message.content)" /></details>
          </template>
          <ChatMarkdown v-else :content="renderContent(message.content)" />

        </template>
      </div>
      <p v-if="busy" role="status" class="empty">正在分析…</p>
    </div>
    <p v-if="error || conversation?.error" role="alert" class="error">{{ error || conversation?.error }}</p>
    <form @submit.prevent="send">
      <textarea v-model="question" rows="4" maxlength="1000" :aria-label="''+shortName+'问题'" :placeholder="academic?'询问真实论文主题、趋势或关联…':'询问某个主题还有哪些我未关注的方向…'" :disabled="busy || initializing" @keydown="composerKeydown" @compositionstart="composing=true" @compositionend="composing=false"></textarea>
      <div class="composer-actions"><small>Enter 发送，Shift+Enter 换行</small><button type="submit" class="send" :disabled="busy || initializing || !question.trim()">{{ busy?'分析中…':academic?'发送问题':'查找遗漏主题' }}</button></div>
    </form>
  </article>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue';
import { api } from '../../services/api';
import ChatMarkdown from '../../components/ChatMarkdown.vue';

interface Suggestion { public_id?: string; name: string; cooccurrence_count: number; my_research_count: number }
interface Message { role: 'user'|'assistant'; content: string; suggestions?: Suggestion[]; plan?: unknown }
interface Conversation { id: string; title: string; updated_at: string; status: 'idle'|'running'; error: string|null; messages: Message[] }
interface HistoryItem { id: string; title: string; updated_at: string; status: string; message_count: number; preview: string }
const emit = defineEmits<{topic: [id: string]}>();
const props = defineProps<{ modelProfileId?: string; academic?: boolean }>();
const examples=['最近一年真实论文数量最多的研究主题有哪些？','与“多模态机器学习应用”共同出现最多的主题有哪些？','“医学教育创新”近90天的论文发表趋势怎样？','比较“医疗人工智能”和“计算药物发现方法”的研究数量','数据库领域最近有哪些真实论文？','概括近一年医学领域的真实研究热点'];
const assistantName=props.academic?'真实学术问答助手':'研究遗漏助手';
const shortName=props.academic?'学术助手':'遗漏助手';
const base = props.academic?'/research-square/academic-conversations':'/research-square/gap-conversations';
const storageKey = props.academic?'research-academic-active-conversation':'research-gap-active-conversation';
const conversation = ref<Conversation|null>(null);
const question = ref(''); const error = ref(''); const posting = ref(false); const initializing = ref(true); const composing = ref(false);
const busy = computed(() => posting.value || conversation.value?.status === 'running');
const history = ref<HistoryItem[]>([]); const historyOpen = ref(false); const historyQuery = ref(''); const historyError = ref('');
const filteredHistory = computed(() => history.value.filter(item => (item.title+' '+item.preview).toLowerCase().includes(historyQuery.value.trim().toLowerCase())));
const messageList = ref<HTMLElement|null>(null);
const deleteTarget = ref<HistoryItem|null>(null); const deleting = ref(false); const deleteError = ref('');
const cancelDeleteButton = ref<HTMLButtonElement|null>(null); const confirmDeleteButton = ref<HTMLButtonElement|null>(null);
const drafts = new Map<string,string>();
let epoch = 0; let timer: ReturnType<typeof setInterval>|undefined; let polling = false; let disposed = false;
function renderContent(text:string){const wrapped=text.trim().match(/^```(?:markdown|md)\s*\n([\s\S]*?)\n```$/i);return wrapped?wrapped[1]:text;}
function remember(id: string) { try { localStorage.setItem(storageKey, id || 'new'); } catch {} }
function scrollBottom() { void nextTick(() => { if(messageList.value) messageList.value.scrollTop = messageList.value.scrollHeight; }); }
async function loadHistory() { try { history.value = await api<HistoryItem[]>(base); historyError.value=''; } catch { historyError.value='历史对话加载失败'; } }
async function toggleHistory() { historyOpen.value=!historyOpen.value; if(historyOpen.value) await loadHistory(); }
function newConversation() { if(busy.value)return; drafts.set(conversation.value?.id || '',question.value); epoch++; conversation.value=null; question.value=drafts.get('') || ''; error.value=''; historyOpen.value=false; remember(''); }
async function openConversation(id: string) {
  if(busy.value)return;
  drafts.set(conversation.value?.id || '',question.value);
  const token=++epoch; initializing.value=true; error.value='';
  try { const result=await api<Conversation>(`${base}/${id}`); if(token!==epoch)return; conversation.value=result; question.value=drafts.get(id)||''; historyOpen.value=false; remember(id); scrollBottom(); }
  catch(e) { if(token===epoch)error.value=e instanceof Error?e.message:'对话加载失败'; }
  finally { if(token===epoch)initializing.value=false; }
}
function composerKeydown(event: KeyboardEvent) {
  if(event.key==='Enter' && !event.shiftKey && !event.isComposing && !composing.value && event.keyCode!==229) { event.preventDefault(); if(!event.repeat)void send(); }
}
async function send() {
  const asked=question.value.trim(); if(!asked || busy.value || initializing.value)return;
  const token=epoch; posting.value=true; error.value='';
  let id=conversation.value?.id;
  try {
    if(!id) { const created=await api<Conversation>(base,{method:'POST'}); id=created.id; if(token!==epoch)return; conversation.value=created; remember(id); }
    conversation.value!.messages.push({role:'user',content:asked}); question.value=''; scrollBottom();
    const result=await api<Conversation>(`${base}/${id}/messages`,{method:'POST',body:JSON.stringify({question:asked,model_profile_id:props.modelProfileId || null,data_source:props.academic?'openalex':'local',days:365})});
    if(token===epoch) { conversation.value=result; scrollBottom(); }
  } catch(e) {
    if(token===epoch) {
      error.value=e instanceof Error?e.message:'分析失败'; question.value=asked;
      if(id) { try { const saved=await api<Conversation>(`${base}/${id}`); if(token===epoch)conversation.value=saved; } catch {} }
    }
  } finally { if(token===epoch)posting.value=false; void loadHistory(); }
}
function askDelete(item: HistoryItem) { deleteTarget.value=item; deleteError.value=''; void nextTick(()=>cancelDeleteButton.value?.focus()); }
function focusDeleteAction() { (document.activeElement===cancelDeleteButton.value?confirmDeleteButton.value:cancelDeleteButton.value)?.focus(); }
async function deleteConversation() {
  if(!deleteTarget.value || deleting.value)return;
  const id=deleteTarget.value.id; deleting.value=true;
  try { await api(`${base}/${id}`,{method:'DELETE'}); if(conversation.value?.id===id) { conversation.value=null; question.value=''; error.value=''; remember(''); } drafts.delete(id); deleteTarget.value=null; await loadHistory(); }
  catch { deleteError.value='删除失败，请重试'; } finally { deleting.value=false; }
}
function dateLabel(value: string) { const date=new Date(value),today=new Date(); if(date.toDateString()===today.toDateString())return '今天'; today.setDate(today.getDate()-1); return date.toDateString()===today.toDateString()?'昨天':date.toLocaleDateString('zh-CN'); }
function timeLabel(value: string) { return new Date(value).toLocaleTimeString('zh-CN',{hour:'2-digit',minute:'2-digit'}); }
async function poll() {
  if(polling || posting.value || conversation.value?.status!=='running')return;
  const id=conversation.value.id,token=epoch; polling=true;
  try { const result=await api<Conversation>(`${base}/${id}`); if(token===epoch) { const changed=result.messages.length!==conversation.value?.messages.length; conversation.value=result; if(changed)scrollBottom(); if(result.status==='idle')void loadHistory(); } } catch { /* Next poll retries a transient network failure. */ } finally { polling=false; }
}
onMounted(()=>{
  // Every entry starts a fresh draft; history is opened only by explicit choice.
  conversation.value=null; question.value=''; initializing.value=false;
  remember('');
  void loadHistory();
  timer=setInterval(poll,1000);
});
onBeforeUnmount(()=>{disposed=true;epoch++;if(timer)clearInterval(timer);});
</script>

<style scoped>
.gap-assistant{position:relative;display:flex;flex-direction:column;height:820px;min-height:0;min-width:0;box-sizing:border-box;padding:20px;background:#fff;border:1px solid #e0e6f2;border-radius:18px;box-shadow:0 9px 25px #2f477012;color:#27344e;font-size:14px;overflow:hidden}
.gap-header{display:flex;justify-content:space-between;align-items:flex-start;gap:10px;flex-shrink:0}.gap-header h2{font-size:18px;margin:0 0 5px}.gap-header small{font-size:14.3333px;color:#8491a9}.header-actions{display:flex;gap:7px;flex-shrink:0}
button{font:inherit;font-size:14.3333px;border:1px solid #d7e1f3;background:#edf3ff;border-radius:7px;padding:8px 12px;color:#3767c5;cursor:pointer}button:disabled{opacity:.5;cursor:default}.header-actions button{width:32px;height:32px;padding:0;display:grid;place-items:center;background:#f8faff;font-size:21px}.header-actions .selected{background:#e2ebff;color:#3568eb}
.assistant-note{flex-shrink:0;padding:10px 12px;border-radius:10px;background:#f4f7ff;color:#667691;font-size:12px;line-height:1.65;margin:12px 0}.conversation-title{flex-shrink:0;display:flex;align-items:center;gap:10px;font-size:15px;font-weight:600;border-bottom:1px solid #111;padding:4px 0 12px;margin-bottom:8px}.conversation-title svg{flex-shrink:0}.conversation-title span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.gap-messages{flex:1;min-height:0;overflow-y:auto;overscroll-behavior:contain;display:flex;flex-direction:column;gap:10px;padding:4px 2px;margin-top:6px}.message{flex-shrink:0;min-width:0;padding:12px;border-radius:12px;font-size:14px;line-height:1.6;overflow-wrap:anywhere}.message.user{background:#eef3ff;margin-left:28px}.message.assistant{background:#f4f8f6;margin-right:20px}.message p{margin:5px 0;font-size:14px;font-weight:400}.user-content{white-space:pre-wrap}.assistant-label{font-size:14px}.gap-suggestion h3{font-size:15px;font-weight:700;margin:14px 0 4px;line-height:1.6}.gap-suggestion p{font-size:14px;font-weight:400;margin:0 0 12px}.analysis-details,.plan-details{margin-top:12px;font-size:13px;color:#60718d}summary{cursor:pointer}.plan-details pre{font-size:11px;white-space:pre-wrap;overflow-wrap:anywhere}.analysis-details :deep(.chat-markdown){font-size:14px}.analysis-details :deep(h1),.analysis-details :deep(h2),.analysis-details :deep(h3),.analysis-details :deep(h4){font-size:15px}.empty{color:#8291a8;font-size:14px;line-height:1.7}.error{font-size:13px;color:#ba3545;margin:8px 0;overflow-wrap:anywhere}
form{flex-shrink:0;display:flex;flex-direction:column;gap:9px;margin-top:12px}textarea{box-sizing:border-box;width:100%;height:98px;resize:none;border:1px solid #d7deed;border-radius:10px;padding:10px;background:#fff;color:#27344e;font-family:inherit;font-size:14.3333px;line-height:1.6}.composer-actions{display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap}.composer-actions small{font-size:12px;color:#8491a9}.send{background:#506bd8;color:#fff;border:0;font-weight:600}
.history-backdrop{position:absolute;inset:60px 0 0;background:#25364c26;z-index:10}.chat-history{position:absolute;z-index:11;top:60px;left:14px;right:14px;max-height:70%;display:flex;flex-direction:column;gap:12px;border:1px solid #dce5f5;border-radius:14px;padding:16px;background:#fff;box-shadow:0 8px 28px #253a5b20;box-sizing:border-box}.chat-history header{display:flex;justify-content:space-between;align-items:center}.chat-history h4{margin:0;font-size:17px}.chat-history>small{font-size:12px;color:#8392a9}.chat-history header button{border:0;padding:2px 5px;background:transparent}.chat-history input{width:100%;min-width:0;border:1px solid #d9e3f4;border-radius:8px;padding:9px;font:inherit;font-size:14px}.conversation-list{overflow:auto;min-height:0}.history-date{font-size:13px;color:#8191ab;margin:10px 4px}.history-item{position:relative}.conversation-row{display:grid;grid-template-columns:minmax(0,1fr) auto;text-align:left;width:100%;gap:6px;border:1px solid transparent;border-radius:9px;padding:10px 36px 10px 10px;margin-bottom:6px;background:#fff;color:#32445f}.conversation-row.active{background:#ebf2ff;border-left:3px solid #477aff}.conversation-row strong{font-size:14px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.conversation-row time{font-size:12px;color:#7b8eab}.conversation-row span{grid-column:1/-1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-size:13px;color:#7b8eab}.conversation-row small{grid-column:1/-1;font-size:12px;color:#8a98af}.delete-conversation{position:absolute;right:5px;bottom:8px;padding:2px 6px;background:transparent;border:0;font-size:19px;color:#7b8eab}.delete-conversation:hover{color:#c63e48;background:#fff0f1}.history-empty{font-size:13px;color:#8795ab}
.delete-overlay{position:absolute;inset:0;z-index:20;background:#25364c55;display:flex;align-items:center;justify-content:center;padding:16px}.delete-dialog{background:#fff;border-radius:14px;padding:20px;max-width:360px;box-shadow:0 10px 30px #25364c33}.delete-dialog h4{margin:0}.delete-dialog p{font-size:14px;line-height:1.7;overflow-wrap:anywhere}.delete-dialog>div{display:flex;justify-content:flex-end;gap:10px}.cancel-delete{background:#e8f6ee;color:#23814f;border-color:#b9dfca}.confirm-delete{background:#d7424c;color:#fff;border-color:#d7424c}
.gap-suggestion .topic-link{padding:0;border:0;background:none;font:inherit;color:#315eb5;text-align:left;line-height:inherit}.topic-link:hover{text-decoration:underline}
.academic-examples{flex-shrink:0;padding:12px;border-radius:12px;background:#f5f7fd;color:#60708d;font-size:12px;margin-bottom:10px}.academic-examples>div{display:flex;flex-wrap:wrap;gap:7px;margin-top:9px}.academic-examples button{padding:7px 10px;border:1px solid #d5def3;background:#fff;color:#4962bb;font-size:11px;text-align:left}.academic-examples button:hover{background:#edf2ff;border-color:#7890e4}
</style>
