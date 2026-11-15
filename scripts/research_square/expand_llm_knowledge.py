"""Incrementally import evidence for LLM directions; safe to rerun and deduplicated by OpenAlex ID."""
import argparse,importlib.util,json,re,sys
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend/src'))
spec=importlib.util.spec_from_file_location('oa',Path(__file__).with_name('import_openalex.py'))
oa=importlib.util.module_from_spec(spec);spec.loader.exec_module(oa)

# slug | Chinese label | English search phrase | evidence expression | explanation
DEFINITIONS='''text-classification|文本分类|text classification|text classification|将文本映射到预定义类别，研究大模型的零样本、少样本分类与领域泛化。
sentiment|情感分析|sentiment analysis|sentiment analysis|识别文本或多模态内容的情感倾向，关注方面级情感与跨领域适应。
stance|立场检测|stance detection|stance detection|判断表达者对指定目标的支持、反对或中立态度，涵盖文本与多模态线索。
sarcasm|讽刺检测|sarcasm detection|sarcasm detection|识别字面表述与真实意图之间的反差，关注语境推理及图文不一致线索。
ner|命名实体识别|named entity recognition|named entity recognition|从文本中识别人名、机构、地点及领域实体，研究提示与结构化抽取。
relation|关系抽取|relation extraction|relation extraction|识别实体之间的语义关系，为结构化知识库与知识图谱提供事实候选。
summarization|文本摘要|text summarization|summarization|压缩长文本并保留关键信息，关注忠实性、覆盖率与长文档理解。
translation|机器翻译|machine translation|machine translation|在不同语言之间生成语义一致的文本，研究多语种能力与低资源语言适应。
qa|问答系统|question answering|question answering|针对问题生成答案，关注证据检索、阅读理解、答案正确性和可追溯性。
reasoning|推理能力|reasoning|reasoning|研究大模型的多步推理、规划和问题求解能力及其可靠性。
math|数学推理|mathematical reasoning|mathematical reasoning|研究数学问题理解、演绎推导、计算与可验证解题过程。
code|代码生成|code generation|code generation|根据自然语言或代码上下文生成程序，关注功能正确性、测试和安全性。
rag|检索增强生成|retrieval augmented generation|retrieval[ -]augmented generation|将外部文档检索与生成结合，研究证据选择、知识更新和回答可追溯性。
agents|智能体与工具调用|tool use agents|tool use|tool calling|agentic|研究模型调用工具、制定计划和执行多步任务的能力。
cot|思维链|chain of thought|chain.of.thought|借助中间推理步骤组织求解，研究推理效果、忠实性与计算成本。
long-context|长上下文|long context|long.context|研究长序列输入的建模、信息定位、记忆与上下文利用效率。
pretraining|预训练|pretraining|pre.?training|通过大规模数据学习通用表示，关注训练目标、数据质量与规模规律。
instruction|指令微调|instruction tuning|instruction tuning|通过任务指令和响应样本提升模型遵循指令及跨任务泛化的能力。
peft|参数高效微调|parameter efficient fine tuning|parameter.efficient|low.rank adaptation|以少量可训练参数适配模型，关注低秩适配和资源效率。
alignment|偏好对齐|preference alignment|preference|RLHF|direct preference optimization|依据人类或模型反馈调整生成偏好，关注帮助性、安全性和对齐偏差。
distillation|知识蒸馏|knowledge distillation|knowledge distillation|将较大模型的能力迁移给较小模型，研究性能与部署成本的平衡。
quantization|模型量化|quantization|quantization|降低模型权重和计算的数值精度，以减少显存和推理成本。
moe|混合专家模型|mixture of experts|mixture.of.experts|通过条件路由激活部分专家网络，研究模型容量、效率与负载均衡。
benchmark|模型评测|evaluation benchmark|benchmark|evaluation|利用基准任务和评价方法衡量模型能力、可靠性、偏差与泛化。
safety|模型安全与越狱|jailbreak safety|jailbreak|研究恶意提示与安全防护，评估拒答行为、攻击迁移及防御可靠性。
privacy|隐私保护|privacy|privacy|研究训练数据泄露、成员推断、隐私风险与保护机制。
bias|偏见与公平性|bias fairness|fairness|social bias|研究模型输出中的社会偏见、群体差异和公平性评估。
multilingual|多语言模型|multilingual|multilingual|研究跨语言理解与生成、语言迁移及低资源语言覆盖。
vqa|视觉问答|visual question answering|visual question answering|根据图像或视频内容回答问题，研究视觉理解和语言推理的结合。
caption|图像描述|image captioning|image captioning|根据图像生成文字描述，关注对象关系、细节覆盖与事实忠实性。
grounding|视觉定位与指代|visual grounding|visual grounding|将语言表达对应到图像中的对象或区域，研究跨模态对齐和空间推理。
video|视频理解|video understanding|video understanding|video.language|研究视频的时序语义、动作、事件及长视频问答。
document|文档理解|document understanding|document understanding|结合文字、版面和图像理解文档，支持信息抽取与文档问答。
mm-retrieval|多模态检索|multimodal retrieval|multimodal retrieval|cross.modal retrieval|在文本、图像等不同模态间检索相关内容，研究统一表示与匹配。
omni|全模态大模型|omni modal|omni.modal|omnimodal|omni multimodal|统一理解或生成文本、图像、音频及视频等多种模态，研究跨模态交互。
audio|音频模型|audio language model|audio.language|audio foundation|large audio|研究音频信号理解与语言建模的结合，涵盖声音事件、语音和音频推理。
speech|语音识别|speech recognition|speech recognition|将语音转换为文本，研究多语种、噪声鲁棒性和语言模型辅助解码。
tts|语音合成|speech synthesis|speech synthesis|text.to.speech|根据文本或条件生成语音，关注自然度、可控性与说话人特征。
speech-dialogue|语音对话|spoken dialogue|spoken dialogue|speech.to.speech|研究语音输入输出的交互系统，关注实时性、轮次管理和自然交流。
music|音乐理解与生成|music generation|music generation|music understanding|研究音乐信号的语义理解、描述与条件生成。
emotion|多模态情绪识别|multimodal emotion recognition|multimodal emotion|结合语音、表情和文本线索识别情绪，研究模态融合和噪声鲁棒性。
embodied|具身智能|embodied intelligence|embodied|研究模型与环境交互，通过感知、规划和行动完成任务。
vla|视觉语言动作模型|vision language action|vision.language.action|将视觉、语言与动作联合建模，用于机器人任务理解和控制。
medical|医学大模型|medical language model|medical|clinical|研究医疗文本、影像与临床任务中的大模型应用及可靠性。
hallucination-mitigation|幻觉缓解|hallucination mitigation|hallucination|研究降低缺乏依据生成内容的方法，包括检索、校验、对齐与解码改进。
uncertainty|不确定性与置信度|uncertainty estimation|uncertainty|calibration|研究模型对答案不确定性的估计、置信度校准和适时拒答。'''

def definitions():
    result=[]
    for line in DEFINITIONS.splitlines():
        parts=line.split('|');slug,name,phrase=parts[:3];description=parts[-1];regex='|'.join(parts[3:-1])
        result.append(dict(id='concept-'+slug,name=name,phrase=phrase,regex=regex,description=description))
    return result

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--per-direction',type=int,default=30);parser.add_argument('--skip-import',action='store_true');args=parser.parse_args()
    if not 1<=args.per_direction<=100:parser.error('per-direction must be 1..100')
    store=oa.ResearchSquareStore();defs=definitions();report={'directions':[],'failed':[]}
    with store.connect() as db:before=db.execute('SELECT COUNT(*) FROM openalex_works').fetchone()[0]
    def fetch(d):
        broad=d['id'] in ['concept-omni','concept-audio','concept-speech-dialogue','concept-music']
        query=d['phrase'] if broad else '('+d['phrase']+') AND ("large language model" OR "multimodal large model" OR "vision language model")'
        with oa.httpx.Client(timeout=60) as client:
            params={'search.title_and_abstract':query,'filter':'from_publication_date:2022-01-01,to_publication_date:2026-11-15,has_abstract:true','per_page':args.per_direction,'select':oa.SELECT_FIELDS,'sort':'cited_by_count:desc'}
            if oa.os.getenv('OPENALEX_API_KEY'):params['api_key']=oa.os.getenv('OPENALEX_API_KEY')
            payload=oa.fetch_page(client,params,attempts=3)
        regex=re.compile(d['regex'],re.I)
        return d,[w for w in payload.get('results',[]) if regex.search(w['title']+' '+(oa.reconstruct_abstract(w.get('abstract_inverted_index')) or ''))]
    with ThreadPoolExecutor(max_workers=3) as pool:
        for task in as_completed([pool.submit(fetch,d) for d in ([] if args.skip_import else defs)]):
            try:
                d,works=task.result();oa.upsert_page(store,works);report['directions'].append({'name':d['name'],'fetched':len(works),'ids':[oa.short_id(w['id']) for w in works]});print(d['name'],len(works),flush=True)
            except Exception as exc:report['failed'].append(type(exc).__name__);print('Import batch failed',type(exc).__name__,flush=True)
    base=re.compile(r'large[ -](?:language|vision.language|multimodal)[ -]models?|\b(?:llms?|mllms?|lvlms?)\b',re.I)
    multi=re.compile(r'multi[ -]?modal|vision[ -]language|visual[ -]language|\b(?:mllms?|lvlms?)\b',re.I)
    with store.connect() as db:
        for d in defs:
            db.execute('INSERT INTO academic_concepts VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,description=excluded.description',(d['id'],d['name'],d['description']))
            db.execute('INSERT OR IGNORE INTO academic_concept_aliases VALUES(?,?)',(d['id'],d['phrase']))
        for identifier,alias in [('concept-llm','LLM'),('concept-llm','大模型'),('concept-llm','large language model'),('concept-mllm','MLLM'),('concept-mllm','multimodal large language model'),('concept-hallucination','hallucination detection'),('concept-omni','全模态'),('concept-audio','音频大模型'),('concept-stance','立场识别'),('concept-sarcasm','讽刺识别')]:db.execute('INSERT OR IGNORE INTO academic_concept_aliases VALUES(?,?)',(identifier,alias))
        for r in db.execute('SELECT id,title,abstract FROM openalex_works').fetchall():
            text=r['title']+' '+(r['abstract'] or '')
            is_llm=bool(base.search(text));related=is_llm or bool(re.search(r'audio.language|audio foundation|omni.modal|omnimodal|vision.language',text,re.I))
            if not related:continue
            matched=[d['id'] for d in defs if re.search(d['regex'],text,re.I)]
            if is_llm:matched.append('concept-llm')
            if is_llm and multi.search(text):matched.append('concept-mllm')
            if is_llm and re.search('hallucinat',text,re.I) and re.search('detect|evaluat|benchmark|assess|identif',text,re.I):matched.append('concept-hallucination')
            for identifier in matched:db.execute('INSERT OR REPLACE INTO academic_concept_works VALUES(?,?,?)',(identifier,r['id'],text))
        report['before']=before;report['after']=db.execute('SELECT COUNT(*) FROM openalex_works').fetchone()[0]
        report['coverage']=[dict(r) for r in db.execute('SELECT c.id,c.name,COUNT(cw.work_id) papers FROM academic_concepts c LEFT JOIN academic_concept_works cw ON cw.concept_id=c.id GROUP BY c.id')]
    dest=ROOT/'.runtime/llm-expansion-report.json';dest.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'before':report['before'],'after':report['after'],'nodes':len(report['coverage']),'empty':[r['name'] for r in report['coverage'] if not r['papers']],'failed':report['failed']},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
