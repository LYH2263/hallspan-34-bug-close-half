<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
const s = ref<any>({})
onMounted(async () => { s.value = await api('/seating/stats?hall_id=1') })
</script>
<template>
  <h1>统计</h1>
  <p class="sub">排座占用与违规汇总 · 封闭/开放互斥：封闭场未排入口关闭，未排必须为 0</p>
  <div style="margin-bottom:0.8rem">
    <span class="badge" :class="s.session_status === 'closed' ? 'badge-bad' : 'badge-ok'">
      {{ s.session_status === 'closed' ? '封闭场 · 未排入口关闭' : '开放场 · 允许现网未排' }}
    </span>
  </div>
  <div class="card" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:1rem">
    <div><div class="muted">已排座</div><div class="stat">{{ s.seated }}</div></div>
    <div>
      <div class="muted">{{ s.session_status === 'closed' ? '未排上（入口关闭）' : '未排上' }}</div>
      <div class="stat">{{ s.unplaced }}</div>
    </div>
    <div><div class="muted">违规数</div><div class="stat">{{ s.violations }}</div></div>
    <div><div class="muted">座位容量</div><div class="stat">{{ s.capacity }}</div></div>
  </div>
</template>
