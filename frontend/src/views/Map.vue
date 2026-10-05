<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api, ApiError } from '../api'
const data = ref<any>(null)
const candidates = ref<any[]>([])
const violKeys = ref<Set<string>>(new Set())
const submitError = ref('')
const submitting = ref(false)
const isClosed = computed(() => data.value?.session_status === 'closed')
const isStale = computed(() => data.value?.stale === true)
async function refreshViolations() {
  try {
    const v = await api('/seating/violations?hall_id=1')
    const keys = new Set<string>()
    for (const x of v.violations || []) {
      if (x.a_id != null) keys.add(String(x.a_id))
      if (x.b_id != null) keys.add(String(x.b_id))
    }
    violKeys.value = keys
  } catch { violKeys.value = new Set() }
}
async function loadLatest() {
  data.value = await api('/seating/latest?hall_id=1')
  await refreshViolations()
}
async function run() {
  submitting.value = true; submitError.value = ''
  try {
    data.value = await api('/seating/run?hall_id=1', { method: 'POST' })
    await refreshViolations()
  } catch (e) {
    if (e instanceof ApiError && e.status === 422) {
      // 封闭场全员落座失败：整场失败、不增方案。失败说明只有封闭场规则本身。
      submitError.value = e.message
    } else {
      submitError.value = e instanceof ApiError ? e.message : String(e)
    }
    await loadLatest()
  } finally { submitting.value = false }
}
onMounted(async () => {
  candidates.value = await api('/candidates')
  await loadLatest()
})
const gridStyle = computed(() => data.value ? ({ gridTemplateColumns: `repeat(${data.value.cols}, 72px)` }) : {})
const cells = computed(() => {
  if (!data.value) return []
  const map = new Map<string, any>()
  for (const a of data.value.assignments || []) map.set(a.row + ',' + a.col, a)
  const out: any[] = []
  for (let r = 0; r < data.value.rows; r++) {
    for (let c = 0; c < data.value.cols; c++) {
      out.push(map.get(r + ',' + c) || { empty: true, row: r, col: c })
    }
  }
  return out
})
function isViol(cell: any) {
  if (cell.empty) return false
  const id = cell.candidate_id ?? cell.id
  return id != null && violKeys.value.has(String(id))
}
function paperClass(pid: number) { return pid % 2 === 0 ? 'b' : 'a' }
</script>
<template>
  <h1>考场课桌网格</h1>
  <p class="sub">课桌网格为主视图 · 左侧考生名册夹板 · 违规课桌高亮 · 场次封闭/开放在提交瞬间按关键标记切换</p>
  <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:0.6rem">
    <button class="btn" :disabled="submitting" @click="run">{{ submitting ? '提交中…' : '提交排座' }}</button>
    <span v-if="data && !isStale" class="badge" :class="isClosed ? 'badge-bad' : 'badge-ok'">
      {{ isClosed ? '封闭场 · 未排入口关闭 · 全员落座' : '开放场 · 允许现网未排' }}
    </span>
    <span v-else-if="data && isStale" class="badge badge-warn">
      关键标记已变更：当前应为{{ data.current_status === 'closed' ? '封闭' : '开放' }}场，下图为旧{{ data.session_status === 'closed' ? '封闭' : '开放' }}图，请重新提交
    </span>
  </div>
  <p v-if="submitError" class="badge badge-bad" style="font-size:0.95rem">{{ submitError }}</p>
  <div class="hs-classroom" style="margin-top:0.85rem">
    <aside class="hs-clipboard">
      <h2>考生名册</h2>
      <div v-for="c in candidates" :key="c.id" class="hs-roster-row">
        <div>
          <div>
            {{ c.name }}
            <span v-if="c.is_key" class="badge badge-bad" style="margin-left:6px">关键</span>
          </div>
          <div class="hs-ticket">{{ c.ticket_no }}</div>
        </div>
        <div>卷{{ c.paper_id }}</div>
      </div>
    </aside>
    <div class="hs-desk-stage" v-if="data">
      <div class="hs-grid-board" :style="gridStyle">
        <div
          v-for="(cell,i) in cells" :key="i"
          class="hs-desk"
          :class="{ empty: cell.empty, 'hs-viol': isViol(cell) }"
        >
          <template v-if="!cell.empty">
            <span class="hs-paper-tag" :class="paperClass(cell.paper_id)">卷{{ cell.paper_id }}</span>
            <div>{{ cell.name }}</div>
          </template>
          <template v-else>·</template>
        </div>
      </div>
      <!-- 只有开放场（且快照未过期）才显示现网未排；封闭场未排入口关闭，未排必须为 0。 -->
      <div v-if="!isClosed && !isStale && (data.unplaced || []).length" class="card" style="margin-top:0.8rem">
        <strong>开放场现网未排（{{ data.unplaced.length }}）：</strong>
        <span v-for="(u,i) in data.unplaced" :key="u.id" style="margin-right:10px">
          {{ u.name }}（{{ u.ticket_no }}）<span v-if="i < data.unplaced.length - 1">、</span>
        </span>
      </div>
      <p v-else-if="isClosed" class="muted" style="margin-top:0.6rem">封闭场未排入口关闭，未排为 0。</p>
      <p v-else-if="isStale" class="muted" style="margin-top:0.6rem">快照已过期，未排信息暂不展示，请重新提交排座。</p>
    </div>
  </div>
</template>
