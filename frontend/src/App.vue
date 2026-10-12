<script setup>
import { computed, onMounted, ref } from 'vue'

const loading = ref(false)
const error = ref('')
const events = ref([])
const filters = ref({ start: '2024-01-01T00:00', end: '2024-01-07T23:59', magnitude: '5' })

const largest = computed(() => events.value.reduce((max, event) => Math.max(max, event.magnitude ?? 0), 0))
const coordinates = computed(() => events.value[0] ? `${events.value[0].latitude?.toFixed(2)}, ${events.value[0].longitude?.toFixed(2)}` : '—')

async function loadEvents() {
  loading.value = true
  error.value = ''
  try {
    const params = new URLSearchParams({
      start: new Date(filters.value.start).toISOString(),
      end: new Date(filters.value.end).toISOString(),
      min_magnitude: filters.value.magnitude,
      limit: '8',
    })
    const response = await fetch(`/api/v1/events?${params}`)
    const payload = await response.json()
    if (!response.ok) throw new Error(payload.detail || 'Не удалось получить события')
    events.value = payload.items
  } catch (requestError) {
    error.value = requestError.message
    events.value = []
  } finally {
    loading.value = false
  }
}

onMounted(loadEvents)
</script>

<template>
  <main>
    <aside class="sidebar">
      <div class="brand"><span class="brand-mark">⌁</span><span>Seismo<span>Scope</span></span></div>
      <nav><a class="active">Обзор</a><a>Каталог событий</a><a>Станции</a><a>Сравнение сигналов</a><a>Аналитика</a></nav>
      <div class="source"><span class="dot"></span> EarthScope FDSN<br /><small>Подключено через API</small></div>
    </aside>
    <section class="content">
      <header><div><p class="eyebrow">ИНФОРМАЦИОННО-АНАЛИТИЧЕСКАЯ СИСТЕМА</p><h1>Сейсмическая активность</h1><p class="sub">Мониторинг событий распределённой сети станций</p></div><div class="utc">UTC<br /><strong>LIVE CATALOGUE</strong></div></header>

      <form class="filters" @submit.prevent="loadEvents">
        <label>Начало<input v-model="filters.start" type="datetime-local" /></label>
        <label>Конец<input v-model="filters.end" type="datetime-local" /></label>
        <label>Магнитуда от<input v-model="filters.magnitude" type="number" min="0" max="10" step="0.1" /></label>
        <button :disabled="loading">{{ loading ? 'Загрузка…' : 'Найти события' }}</button>
      </form>

      <p v-if="error" class="error">{{ error }}. Проверьте подключение EarthScope и попробуйте ещё раз.</p>
      <section class="metrics">
        <article><span>Найдено событий</span><strong>{{ events.length }}</strong><small>за выбранный период</small></article>
        <article><span>Макс. магнитуда</span><strong>{{ largest ? `M ${largest.toFixed(1)}` : '—' }}</strong><small>по результатам поиска</small></article>
        <article><span>Выбранная область</span><strong>{{ coordinates }}</strong><small>координаты первого события</small></article>
      </section>

      <section class="workspace">
        <article class="panel map-panel"><div class="panel-head"><h2>Карта событий</h2><span>ЭПИЦЕНТРЫ</span></div><div class="map"><div class="grid"></div><div v-for="(event, index) in events.slice(0, 6)" :key="event.id" class="quake" :style="{ left: `${17 + (index * 13) % 70}%`, top: `${25 + (index * 19) % 52}%`" :title="event.place"><i :style="{ width: `${10 + (event.magnitude || 0) * 2}px`, height: `${10 + (event.magnitude || 0) * 2}px` }"></i></div><p v-if="!loading && !events.length">Нет событий для отображения</p><span class="map-label">SEISMIC ACTIVITY MAP</span></div></article>
        <article class="panel list-panel"><div class="panel-head"><h2>События</h2><span>{{ events.length }} НАЙДЕНО</span></div><div v-if="loading" class="empty">Запрашиваем каталог…</div><div v-else-if="!events.length" class="empty">Выберите период и запустите поиск.</div><button v-else v-for="event in events" :key="event.id" class="event"><b>M {{ event.magnitude?.toFixed(1) ?? '—' }}</b><span>{{ event.place }}<small>{{ new Date(event.time).toLocaleString('ru-RU', { timeZone: 'UTC' }) }} · {{ event.depth_km ?? '—' }} км</small></span><em>›</em></button></article>
      </section>

      <section class="panel wave"><div class="panel-head"><h2>Сравнение сигналов</h2><span>СКОРО БУДЕТ ДОСТУПНО</span></div><div class="wave-lines"><svg viewBox="0 0 900 110" preserveAspectRatio="none"><path d="M0 55 H110 l8 -10 8 20 8 -33 8 50 8 -23 8 8 H270 l8 -12 8 25 8 -48 8 73 8 -38 8 18 H470 l8 -9 8 19 8 -39 8 57 8 -29 8 11 H900" /></svg><div><span>IU.ANMO</span><span>II.KURK</span><span>TA.A25A</span></div></div></section>
    </section>
  </main>
</template>
