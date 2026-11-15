<template>
  <div class="topic-graph-shell">
    <div class="graph-toolbar">
      <span><i class="activity low"></i>近期活跃度较低</span>
      <span><i class="activity middle"></i>近期活跃度中等</span>
      <span><i class="activity high"></i>近期活跃度较高</span>
      <span class="edge-hint">线越粗，主题共同出现关系越强</span>
      <button type="button" @click="resetView">重置视图</button>
    </div>
    <div v-show="data.nodes.length" ref="container" class="topic-graph" role="img"
      aria-label="可拖拽、可缩放的研究主题力导向知识图谱"></div>
    <p v-if="!data.nodes.length" class="empty">当前筛选条件下没有可绘制的主题关系。</p>
    <p v-else class="interaction-hint">拖动节点调整位置 · 滚轮缩放 · 拖动空白处平移 · 点击节点查看关联导入记录</p>
  </div>
</template>

<script setup lang="ts">
import { GraphChart } from 'echarts/charts';
import { TooltipComponent } from 'echarts/components';
import { init, use, type ECharts } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';

use([GraphChart, TooltipComponent, CanvasRenderer]);

export interface TopicGraphNode {
  id: string;
  name: string;
  heat: number;
  recent_activity: number;
  research_count: number;
  average_started_at: string;
  latest_started_at: string;
}
export interface TopicGraphEdge {
  source: string;
  target: string;
  cooccurrence_count: number;
  relation_score: number;
}
export interface TopicGraphData {
  nodes: TopicGraphNode[];
  edges: TopicGraphEdge[];
}

const props = withDefaults(defineProps<{ data: TopicGraphData; periodDays: number; dataSource?: 'local'|'openalex' }>(), { dataSource: 'local' });
const emit = defineEmits<{ select: [node: TopicGraphNode] }>();
const container = ref<HTMLDivElement>();
let chart: ECharts | undefined;
let resizeObserver: ResizeObserver | undefined;
let clickBound = false;

function escapeHtml(value: unknown) {
  return String(value ?? '').replace(/[&<>'"]/g, character => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;',
  }[character] ?? character));
}

function range(values: number[]) {
  return { min: Math.min(...values), max: Math.max(...values) };
}

function scale(value: number, min: number, max: number, low: number, high: number) {
  if (max <= min) return (low + high) / 2;
  return low + (Math.sqrt(Math.max(0, value - min)) / Math.sqrt(max - min)) * (high - low);
}

function activityColor(value: number, min: number, max: number) {
  if (max <= min) return '#b36f73';
  const ratio = Math.max(0, Math.min(1, (value - min) / (max - min)));
  const low = [166, 174, 188];
  const high = [222, 63, 63];
  const rgb = low.map((channel, index) => Math.round(channel + (high[index] - channel) * ratio));
  return `rgb(${rgb.join(',')})`;
}

function render() {
  if (!container.value || !props.data.nodes.length) return;
  chart ??= init(container.value, undefined, { renderer: 'canvas' });
  if (!clickBound) {
    chart.on('click', parameters => {
      if (parameters.dataType !== 'node') return;
      const node = (parameters.data as any)?.raw as TopicGraphNode | undefined;
      if (node?.id) emit('select', node);
    });
    clickBound = true;
  }
  const activityRange = range(props.data.nodes.map(node => node.recent_activity));
  const countRange = range(props.data.nodes.map(node => node.research_count));
  const scores = props.data.edges.map(edge => edge.relation_score);
  const scoreRange = scores.length ? range(scores) : { min: 0, max: 1 };
  const labelIds = new Set([...props.data.nodes]
    .sort((a, b) => b.heat - a.heat).slice(0, 12).map(node => node.id));

  chart.setOption({
    animationDurationUpdate: 500,
    tooltip: {
      trigger: 'item',
      confine: true,
      formatter: (parameters: any) => {
        if (parameters.dataType === 'edge') {
          const edge = parameters.data as TopicGraphEdge;
          return `<b>主题关联</b><br/>共同研究：${edge.cooccurrence_count}<br/>关联强度：${edge.relation_score.toFixed(3)}`;
        }
        const node = parameters.data.raw as TopicGraphNode;
        const countLabel = props.dataSource === 'openalex' ? '真实论文' : '关联研究';
        const averageLabel = props.dataSource === 'openalex' ? '平均发表时间' : '平均发起时间';
        const latestLabel = props.dataSource === 'openalex' ? '最近发表时间' : '最近发起时间';
        return `<b>${escapeHtml(node.name)}</b><br/>最近 ${props.periodDays} 天近期活跃度：${node.recent_activity.toFixed(2)}<br/>${countLabel}：${node.research_count}<br/>${averageLabel}：${escapeHtml(node.average_started_at || '未知')}<br/>${latestLabel}：${escapeHtml(node.latest_started_at || '未知')}`;
      },
    },
    series: [{
      type: 'graph',
      layout: 'force',
      roam: true,
      draggable: true,
      cursor: 'grab',
      data: props.data.nodes.map(node => ({
        id: node.id,
        name: node.name,
        value: node.heat,
        raw: node,
        symbolSize: scale(node.research_count, countRange.min, countRange.max, 24, 66),
        itemStyle: {
          color: activityColor(node.recent_activity, activityRange.min, activityRange.max),
          borderColor: '#ffffff', borderWidth: 2, shadowBlur: 10, shadowColor: '#354d7833',
        },
        label: { show: labelIds.has(node.id) },
      })),
      links: props.data.edges.map(edge => ({
        ...edge,
        lineStyle: {
          width: scale(edge.relation_score, scoreRange.min, scoreRange.max, .8, 5),
          opacity: scale(edge.relation_score, scoreRange.min, scoreRange.max, .16, .72),
          color: '#6e82ad', curveness: .08,
        },
      })),
      force: { repulsion: 260, gravity: .08, edgeLength: [90, 210], friction: .68 },
      label: { position: 'right', color: '#2a3853', fontSize: 11, distance: 5 },
      edgeSymbol: ['none', 'none'],
      emphasis: {
        focus: 'adjacency',
        label: { show: true, fontWeight: 700 },
        lineStyle: { opacity: .95 },
      },
      blur: { itemStyle: { opacity: .18 }, lineStyle: { opacity: .05 }, label: { show: false } },
    }],
  }, true);
}

function resetView() {
  chart?.dispatchAction({ type: 'restore' });
  render();
}

onMounted(async () => {
  await nextTick();
  render();
  if (container.value) {
    resizeObserver = new ResizeObserver(() => chart?.resize());
    resizeObserver.observe(container.value);
  }
});
watch(() => props.data, async () => { await nextTick(); render(); }, { deep: true });
onBeforeUnmount(() => { resizeObserver?.disconnect(); chart?.dispose(); chart = undefined; clickBound = false; });
</script>

<style scoped>
.topic-graph-shell{position:relative}.topic-graph{width:100%;height:680px;border-radius:14px;background:radial-gradient(circle at center,#f4f7ff,#fff 72%)}
.graph-toolbar{display:flex;align-items:center;gap:12px;min-height:30px;margin:-4px 0 6px;color:#75839b;font-size:11px;flex-wrap:wrap}.graph-toolbar span{display:flex;align-items:center;gap:4px}.graph-toolbar .edge-hint{margin-left:6px}.graph-toolbar button{margin-left:auto;border:1px solid #d7deed;background:#fff;color:#4b61a8;border-radius:7px;padding:5px 9px;cursor:pointer}.activity{display:inline-block;width:9px;height:9px;border-radius:50%}.activity.low{background:#a6aebc}.activity.middle{background:#c77578}.activity.high{background:#de3f3f}.interaction-hint{text-align:center;color:#8b97aa;font-size:10px;margin:5px 0 0}.empty{color:#8a96aa;text-align:center;padding:80px 10px}
@media(max-width:760px){.topic-graph{height:360px}.graph-toolbar .edge-hint{display:none}}
</style>
