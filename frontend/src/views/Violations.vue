<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
const viols = ref<any[]>([])
const unplaced = ref<any[]>([])
const status = ref('')
onMounted(async () => {
  const res = await api('/seating/violations?hall_id=1')
  viols.value = res.violations; unplaced.value = res.unplaced; status.value = res.session_status
})
</script>
<template>
  <h1>违规</h1>
  <p class="sub">间距不足或同试卷四邻相邻</p>
  <p>
    <span class="badge" :class="status === 'closed' ? 'badge-bad' : 'badge-ok'">
      {{ status === 'closed' ? '封闭场 · 未排入口关闭' : '开放场 · 允许现网未排' }}
    </span>
  </p>
  <div class="card">
    <table>
      <thead><tr><th>类型</th><th>考生A</th><th>考生B</th><th>说明</th></tr></thead>
      <tbody>
        <tr v-for="(v,i) in viols" :key="i">
          <td>{{ v.kind }}</td><td>{{ v.a_id }}</td><td>{{ v.b_id }}</td><td>{{ v.detail }}</td>
        </tr>
      </tbody>
    </table>
    <p v-if="!viols.length" class="muted">无违规</p>
  </div>
  <!-- 仅开放场展示现网未排；封闭场未排入口关闭，该区块不出现。 -->
  <div class="card" v-if="status !== 'closed' && unplaced.length">
    <h3>开放场现网未排</h3>
    <div v-for="u in unplaced" :key="u.id">{{ u.name }}（{{ u.ticket_no }}）</div>
  </div>
  <p class="muted">列表条数与分类数字可分开累计</p>
</template>
