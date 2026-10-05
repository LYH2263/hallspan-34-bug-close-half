<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api, ApiError } from '../api'
const rows = ref<any[]>([])
const busy = ref<number | null>(null)
const error = ref('')
async function load() { rows.value = await api('/candidates') }
async function toggle(r: any) {
  busy.value = r.id; error.value = ''
  try {
    await api(`/candidates/${r.id}`, { method: 'PATCH', body: JSON.stringify({ is_key: !r.is_key }) })
    await load()
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : String(e)
  } finally { busy.value = null }
}
onMounted(load)
</script>
<template>
  <h1>考生名册</h1>
  <p class="sub">夹板名册样式 · 关键考生标记决定下一次提交排座时的场次状态：有标记则封闭，无标记则开放</p>
  <p v-if="error" class="badge badge-bad">{{ error }}</p>
  <div class="hs-clipboard" style="max-width:520px">
    <h2>考生名册 · Clipboard</h2>
    <div v-for="r in rows" :key="r.id" class="hs-roster-row">
      <div>
        <div>
          {{ r.name }}
          <span v-if="r.is_key" class="badge badge-bad" style="margin-left:6px">关键</span>
        </div>
        <div class="hs-ticket">{{ r.ticket_no }}</div>
      </div>
      <div style="display:flex;align-items:center;gap:8px">
        <div class="muted">卷{{ r.paper_id }} · 室{{ r.hall_id }}</div>
        <button class="btn" style="padding:2px 10px;font-size:0.78rem"
                :disabled="busy === r.id" @click="toggle(r)">
          {{ r.is_key ? '取消关键' : '标为关键' }}
        </button>
      </div>
    </div>
  </div>
</template>
