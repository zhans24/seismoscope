<script setup>
import { computed, onMounted, ref } from 'vue'
import WorldMap from './components/WorldMap.vue'

const page = ref('overview')
const catalogueState = ref('initial')
const catalogueError = ref('')
const events = ref([])
const selectedCountry = ref(null)
const activeEvent = ref(null)
const modal = ref(false)
const eventReturnPage = ref('overview')
const lastUpdated = ref(null)
const stations = ref([])
const selectedStations = ref([])
const stationLoading = ref(false)
const analysisJob = ref(null)
const analysisError = ref('')

function localDateInput(date) {
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16)
}

const now = new Date()
const filters = ref({
  start: localDateInput(new Date(now.getTime() - 7 * 86400000)),
  end: localDateInput(now),
  magnitude: '5',
})
const analysisOptions = ref({ channel: 'BHZ', seconds_before: 60, seconds_after: 300, filter_low_hz: 0.5, filter_high_hz: 8, normalize: false })
const jobLabels = { pending: 'в очереди', running: 'обработка', succeeded: 'готово', failed: 'ошибка' }
const largest = computed(() => events.value.reduce((max, event) => Math.max(max, event.magnitude ?? 0), 0))
const eventCountLabel = computed(() => catalogueState.value === 'loading' || catalogueState.value === 'initial' ? 'Загрузка данных' : `${events.value.length} ${events.value.length === 1 ? 'событие' : events.value.length < 5 ? 'события' : 'событий'}`)
const plotPeak = computed(() => Math.max(...(analysisJob.value?.traces ?? []).map((trace) => trace.metrics.peak_amplitude_counts), 1e-9))
const plotOptions = computed(() => analysisJob.value?.options ?? analysisOptions.value)
const missingWaveforms = computed(() => analysisJob.value?.station_results?.filter((result) => result.status === 'no_data') ?? [])
const stationErrors = computed(() => analysisJob.value?.station_results?.filter((result) => result.status === 'error') ?? [])
const jobSummary = computed(() => {
  if (!analysisJob.value) return ''
  if (analysisJob.value.status === 'failed' && missingWaveforms.value.length && !stationErrors.value.length) return 'записи не найдены'
  if (analysisJob.value.status === 'succeeded' && missingWaveforms.value.length) return 'готово частично'
  return jobLabels[analysisJob.value.status] ?? analysisJob.value.status
})

function formatEventTime(value) {
  if (!value) return 'Время не указано'
  return new Intl.DateTimeFormat('ru-RU', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit', timeZone: 'UTC' }).format(new Date(value))
}

function formatDepth(value) {
  return value === null || value === undefined ? '—' : `${Number(value).toFixed(value % 1 ? 1 : 0)} км`
}

function catalogueMessage(detail) {
  if (detail === 'USGS catalogue is temporarily unavailable') return 'Каталог USGS временно недоступен. Повторите запрос через несколько минут.'
  if (detail === 'start must be earlier than end') return 'Дата начала должна быть раньше даты окончания.'
  if (detail === 'all country bounds must be provided together') return 'Не удалось применить границы выбранной страны. Повторите выбор на карте.'
  return typeof detail === 'string' ? detail : 'Не удалось получить данные каталога. Повторите запрос.'
}

async function load(bounds = selectedCountry.value?.bounds ?? null) {
  catalogueState.value = 'loading'
  catalogueError.value = ''
  try {
    const params = new URLSearchParams({ start: new Date(filters.value.start).toISOString(), end: new Date(filters.value.end).toISOString(), min_magnitude: filters.value.magnitude, limit: '40' })
    if (bounds) Object.entries(bounds).forEach(([key, value]) => params.set(key.replace(/[A-Z]/g, (letter) => `_${letter.toLowerCase()}`), value))
    const response = await fetch(`/api/v1/events?${params}`)
    const data = await response.json()
    if (!response.ok) throw new Error(catalogueMessage(data.detail))
    events.value = data.items
    catalogueState.value = data.items.length ? 'ready' : 'empty'
    lastUpdated.value = new Date()
  } catch (cause) {
    events.value = []
    catalogueError.value = catalogueMessage(cause.message)
    catalogueState.value = 'error'
  }
}

async function chooseCountry(country) {
  selectedCountry.value = country
  modal.value = true
  await load(country.bounds)
}

function resetCountryFilter() {
  selectedCountry.value = null
  modal.value = false
  load(null)
}

async function inspectEvent(event) {
  eventReturnPage.value = page.value
  activeEvent.value = event
  page.value = 'event'
  stationLoading.value = true
  stations.value = []
  selectedStations.value = []
  analysisJob.value = null
  analysisError.value = ''
  try {
    const params = new URLSearchParams({ latitude: event.latitude, longitude: event.longitude, at: event.time, radius_km: '1500', limit: '12' })
    const response = await fetch(`/api/v1/stations/nearby?${params}`)
    const data = await response.json()
    if (!response.ok) throw new Error(data.detail || 'Не удалось получить список станций.')
    stations.value = data.items
  } catch (cause) {
    analysisError.value = cause.message
  } finally {
    stationLoading.value = false
  }
}

function toggleStation(station) {
  const key = `${station.network}.${station.station}`
  if (selectedStations.value.includes(key)) selectedStations.value = selectedStations.value.filter((value) => value !== key)
  else if (selectedStations.value.length < 5) selectedStations.value = [...selectedStations.value, key]
}

async function startAnalysis() {
  analysisError.value = ''
  try {
    const chosen = stations.value.filter((station) => selectedStations.value.includes(`${station.network}.${station.station}`))
    const response = await fetch('/api/v1/analyses', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ event: activeEvent.value, stations: chosen, ...analysisOptions.value }) })
    const data = await response.json()
    if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Проверьте параметры обработки.')
    analysisJob.value = data
    await pollAnalysis(data.id)
  } catch (cause) {
    analysisError.value = cause.message
  }
}

async function pollAnalysis(id) {
  for (let attempt = 0; attempt < 90; attempt += 1) {
    await new Promise((resolve) => setTimeout(resolve, 3000))
    if (page.value !== 'event' || analysisJob.value?.id !== id) return
    try {
      const response = await fetch(`/api/v1/analyses/${id}`)
      const data = await response.json()
      if (!response.ok) throw new Error(data.detail || 'Не удалось получить результат обработки.')
      analysisJob.value = data
      if (['succeeded', 'failed'].includes(data.status)) return
    } catch (cause) {
      analysisError.value = cause.message
      return
    }
  }
  analysisError.value = 'Обработка занимает больше ожидаемого времени. Проверьте результат позже.'
}

function tracePoints(trace) {
  const values = trace.series.values
  if (!values.length) return ''
  const windowStart = new Date(activeEvent.value.time).getTime() - plotOptions.value.seconds_before * 1000
  const windowDuration = (plotOptions.value.seconds_before + plotOptions.value.seconds_after) * 1000
  const traceStart = new Date(trace.start_time).getTime()
  const amplitudeScale = trace.series.normalized ? 1 : plotPeak.value
  return values.map((value, index) => `${((traceStart - windowStart + index * trace.series.step_seconds * 1000) / windowDuration) * 700},${55 - (value / amplitudeScale) * 43}`).join(' ')
}

const originX = computed(() => (plotOptions.value.seconds_before / (plotOptions.value.seconds_before + plotOptions.value.seconds_after)) * 700)

onMounted(() => load(null))
</script>

<template>
  <main>
    <header class="topbar">
      <button class="brand" aria-label="SeismoScope: к карте землетрясений" @click="page = 'overview'">SEISMO<span>SCOPE</span></button>
      <p>Глобальный каталог сейсмических событий</p>
      <span class="source-mark">Источник: USGS</span>
    </header>

    <section v-if="page === 'overview'" class="overview">
      <div class="intro">
        <div><p class="eyebrow">КАТАЛОГ ЗЕМЛЕТРЯСЕНИЙ</p><h1>Землетрясения<br />по всему миру</h1></div>
        <p>Найдите событие, изучите его положение на карте и сравните записи ближайших станций.</p>
      </div>

      <section class="map-workspace" aria-labelledby="map-title">
        <form class="filters" @submit.prevent="load()">
          <label>Начало периода<input v-model="filters.start" type="datetime-local" required /></label>
          <label>Конец периода<input v-model="filters.end" type="datetime-local" required /></label>
          <label>Минимальная магнитуда<input v-model="filters.magnitude" type="number" min="0" max="10" step=".1" /></label>
          <button class="primary-action" :disabled="catalogueState === 'loading'">{{ catalogueState === 'loading' ? 'Обновляем…' : 'Обновить данные' }}</button>
          <button v-if="selectedCountry" class="text-action" type="button" @click="resetCountryFilter">Сбросить страну</button>
        </form>
        <div class="map-heading">
          <div><p class="eyebrow">ИНТЕРАКТИВНАЯ КАРТА</p><h2 id="map-title">Карта землетрясений</h2></div>
          <dl class="map-summary" aria-live="polite"><div><dt>Найдено</dt><dd>{{ catalogueState === 'loading' || catalogueState === 'initial' ? '—' : events.length }}</dd></div><div><dt>Максимум</dt><dd>{{ catalogueState === 'loading' || !events.length ? '—' : `M ${largest.toFixed(1)}` }}</dd></div></dl>
        </div>
        <div class="map-frame" :class="{ 'is-loading': catalogueState === 'initial' || catalogueState === 'loading' }">
          <WorldMap :events="events" :active-country-id="selectedCountry?.id" :active-event-id="activeEvent?.id" @select-country="chooseCountry" @select-event="inspectEvent" />
          <div v-if="catalogueState === 'initial' || catalogueState === 'loading'" class="map-loading" role="status"><span></span>Получаем события из USGS…</div>
          <div v-else-if="catalogueState === 'error'" class="map-message map-error" role="alert"><strong>Не удалось обновить карту</strong><span>{{ catalogueError }}</span><button class="secondary-action" @click="load()">Повторить запрос</button></div>
          <div v-else-if="catalogueState === 'empty'" class="map-message"><strong>Событий не найдено</strong><span>Попробуйте увеличить период или снизить минимальную магнитуду.</span></div>
        </div>
        <div class="map-caption"><span>Размер точки соответствует магнитуде.</span><span>Выберите страну для сводки или эпицентр для анализа.</span></div>
      </section>

      <section class="catalogue" aria-labelledby="catalogue-title">
        <div class="section-heading"><div><p class="eyebrow">КАТАЛОГ</p><h2 id="catalogue-title">Землетрясения за выбранный период</h2></div><span class="catalogue-meta">{{ eventCountLabel }}<template v-if="lastUpdated && catalogueState === 'ready'"> · обновлено {{ formatEventTime(lastUpdated) }} UTC</template></span></div>
        <div v-if="catalogueState === 'initial' || catalogueState === 'loading'" class="event-skeleton" aria-label="Загрузка списка событий"><span v-for="index in 5" :key="index"></span></div>
        <div v-else-if="catalogueState === 'error'" class="catalogue-state error-state"><strong>Каталог недоступен</strong><p>{{ catalogueError }}</p><button class="secondary-action" @click="load()">Повторить запрос</button></div>
        <div v-else-if="catalogueState === 'empty'" class="catalogue-state"><strong>Нет событий по заданным условиям</strong><p>Измените даты или минимальную магнитуду и обновите данные.</p></div>
        <div v-else class="event-list" role="list">
          <div class="event-list-head" aria-hidden="true"><span>Время (UTC)</span><span>Магнитуда</span><span>Эпицентр</span><span>Глубина</span><span></span></div>
          <button v-for="event in events" :key="event.id" class="event-row" :class="{ selected: activeEvent?.id === event.id }" role="listitem" :aria-label="`Открыть анализ: ${event.place}`" @click="inspectEvent(event)"><time :datetime="event.time">{{ formatEventTime(event.time) }}</time><b>M {{ event.magnitude?.toFixed(1) ?? '—' }}</b><span>{{ event.place || 'Место не указано' }}</span><i>{{ formatDepth(event.depth_km) }}</i><em aria-hidden="true">→</em></button>
        </div>
      </section>
    </section>

    <section v-else-if="page === 'detail'" class="detail-page">
      <button class="back" @click="page = 'overview'">← Вернуться к карте</button>
      <p class="eyebrow">СВОДКА ПО СТРАНЕ</p><h1>{{ selectedCountry?.name }}</h1><p class="detail-lead">События с магнитудой от {{ filters.magnitude }} за выбранный период.</p>
      <div class="stats"><div><span>Событий</span><strong>{{ events.length }}</strong></div><div><span>Максимальная магнитуда</span><strong>{{ largest ? `M ${largest.toFixed(1)}` : '—' }}</strong></div><div><span>Источник</span><strong>USGS</strong></div></div>
      <h2>Список событий</h2>
      <div v-if="!events.length" class="catalogue-state"><strong>Событий нет</strong><p>Измените параметры поиска на карте.</p></div>
      <div v-else class="event-list detail-list"><button v-for="event in events" :key="event.id" class="event-row" :aria-label="`Открыть анализ: ${event.place}`" @click="inspectEvent(event)"><time :datetime="event.time">{{ formatEventTime(event.time) }}</time><b>M {{ event.magnitude?.toFixed(1) ?? '—' }}</b><span>{{ event.place || 'Место не указано' }}</span><i>{{ formatDepth(event.depth_km) }}</i><em aria-hidden="true">→</em></button></div>
    </section>

    <section v-else class="detail-page event-page">
      <button class="back" @click="page = eventReturnPage">← Вернуться к списку</button>
      <p class="eyebrow">АНАЛИЗ СОБЫТИЯ</p><h1>{{ activeEvent?.place || 'Место не указано' }}</h1><p class="detail-lead">{{ formatEventTime(activeEvent?.time) }} UTC · M {{ activeEvent?.magnitude ?? '—' }} · глубина {{ formatDepth(activeEvent?.depth_km) }}</p>
      <section class="analysis-section" aria-labelledby="stations-title">
        <div class="section-heading"><div><p class="eyebrow">1. ВЫБОР СТАНЦИЙ</p><h2 id="stations-title">Ближайшие станции</h2></div><span>{{ selectedStations.length }} из 5 выбрано</span></div>
        <p class="section-note">Доступность записи за нужное время проверяется при загрузке.</p><p v-if="stationLoading" class="loading-line" role="status">Ищем станции EarthScope…</p>
        <div v-else-if="!stations.length && !analysisError" class="catalogue-state"><strong>Станции не найдены</strong><p>В радиусе 1500 км нет станций с каналом BHZ.</p></div>
        <div v-else class="station-list"><label v-for="station in stations" :key="`${station.network}.${station.station}`" class="station-option"><input type="checkbox" :checked="selectedStations.includes(`${station.network}.${station.station}`)" :disabled="selectedStations.length >= 5 && !selectedStations.includes(`${station.network}.${station.station}`)" @change="toggleStation(station)" /><b>{{ station.network }}.{{ station.station }}</b><span>{{ station.site_name || 'Название не указано' }}</span><small>{{ station.distance_km }} км</small></label></div>
      </section>
      <section class="analysis-section" aria-labelledby="parameters-title">
        <div class="section-heading"><div><p class="eyebrow">2. ПАРАМЕТРЫ</p><h2 id="parameters-title">Обработка записи</h2></div></div>
        <div class="analysis-controls"><label>Канал<input v-model="analysisOptions.channel" maxlength="3" /></label><label>До события, с<input v-model.number="analysisOptions.seconds_before" type="number" min="10" max="600" /></label><label>После события, с<input v-model.number="analysisOptions.seconds_after" type="number" min="30" max="1800" /></label><label>Фильтр от, Гц<input v-model.number="analysisOptions.filter_low_hz" type="number" step=".1" min=".1" /></label><label>Фильтр до, Гц<input v-model.number="analysisOptions.filter_high_hz" type="number" step=".1" min=".2" /></label><label class="check-label"><input v-model="analysisOptions.normalize" type="checkbox" /> Нормировать амплитуды</label></div>
        <button class="primary-action" :disabled="!selectedStations.length || ['pending', 'running'].includes(analysisJob?.status)" @click="startAnalysis">Загрузить и сравнить записи</button>
      </section>
      <p v-if="analysisError" class="inline-error" role="alert">{{ analysisError }}</p>
      <div v-if="analysisJob" class="job-status" role="status"><b>Статус: {{ jobSummary }}</b><p v-if="missingWaveforms.length">Нет записи за этот интервал: {{ missingWaveforms.map((result) => result.station).join(', ') }}. Выберите другие станции или повторите запрос позже.</p><p v-if="stationErrors.length">Ошибка загрузки: {{ stationErrors.map((result) => `${result.station}: ${result.message}`).join('; ') }}</p><p v-if="analysisJob.error && !analysisJob.station_results?.length">{{ analysisJob.error }}</p></div>
      <section v-if="analysisJob?.traces?.length" class="analysis-section traces" aria-labelledby="traces-title">
        <div class="section-heading"><div><p class="eyebrow">3. РЕЗУЛЬТАТ</p><h2 id="traces-title">Сравнение сигналов</h2></div></div><p class="section-note">Вертикальная линия — время события. Оценка прихода предварительная.</p>
        <div v-for="trace in analysisJob.traces" :key="trace.station" class="trace"><div class="trace-head"><b>{{ trace.station }} · {{ trace.channel }}</b><span>пик {{ trace.metrics.peak_amplitude_counts }} · SNR {{ trace.metrics.snr_db ?? '—' }} dB · приход {{ trace.metrics.arrival_from_origin_seconds ?? '—' }} с</span></div><svg viewBox="0 0 700 110" preserveAspectRatio="none" :aria-label="`Сейсмограмма ${trace.station}`" role="img"><line x1="0" y1="55" x2="700" y2="55" /><line class="origin-line" :x1="originX" y1="0" :x2="originX" y2="110" /><polyline :points="tracePoints(trace)" /></svg><small>Начало {{ trace.start_time }} · длительность {{ trace.metrics.duration_seconds }} с · шаг {{ trace.series.step_seconds.toFixed(3) }} с</small></div>
      </section>
    </section>

    <div v-if="modal" class="veil" @click.self="modal = false"><section class="modal" role="dialog" aria-modal="true" :aria-label="`Сводка: ${selectedCountry?.name}`" @keydown.esc="modal = false"><button class="x" aria-label="Закрыть" @click="modal = false">×</button><p class="eyebrow">ВЫБРАННАЯ СТРАНА</p><h2>{{ selectedCountry?.name }}</h2><p>События в границах страны за выбранный период.</p><div class="modalstats"><span>Событий<strong>{{ catalogueState === 'loading' ? '…' : events.length }}</strong></span><span>Максимальная магнитуда<strong>{{ catalogueState === 'loading' ? '…' : (largest ? `M ${largest.toFixed(1)}` : '—') }}</strong></span></div><button class="primary-action" :disabled="catalogueState === 'loading'" @click="modal = false; page = 'detail'">Открыть сводку</button></section></div>
  </main>
</template>
