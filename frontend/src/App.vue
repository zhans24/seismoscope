<script setup>
import { computed, onMounted, ref } from 'vue'
import WorldMap from './components/WorldMap.vue'

const page = ref('overview')
const loading = ref(false)
const error = ref('')
const events = ref([])
const selectedCountry = ref(null)
const modal = ref(false)
const activeEvent = ref(null)
const eventReturnPage = ref('overview')
const stations = ref([])
const selectedStations = ref([])
const stationLoading = ref(false)
const analysisJob = ref(null)
const analysisError = ref('')
const jobLabels = { pending: 'в очереди', running: 'обработка', succeeded: 'готово', failed: 'ошибка' }

function localDateInput(date) {
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16)
}

const now = new Date()
const filters = ref({
  start: localDateInput(new Date(now.getTime() - 7 * 86400000)),
  end: localDateInput(now),
  magnitude: '5',
})
const analysisOptions = ref({
  channel: 'BHZ',
  seconds_before: 60,
  seconds_after: 300,
  filter_low_hz: 0.5,
  filter_high_hz: 8,
  normalize: false,
})
const largest = computed(() => events.value.reduce((max, event) => Math.max(max, event.magnitude ?? 0), 0))
const plotPeak = computed(() => Math.max(
  ...(analysisJob.value?.traces ?? []).map((trace) => trace.metrics.peak_amplitude_counts),
  1e-9,
))
const plotOptions = computed(() => analysisJob.value?.options ?? analysisOptions.value)

async function load(bounds = null) {
  loading.value = true
  error.value = ''
  try {
    const params = new URLSearchParams({
      start: new Date(filters.value.start).toISOString(),
      end: new Date(filters.value.end).toISOString(),
      min_magnitude: filters.value.magnitude,
      limit: '40',
    })
    if (bounds) {
      Object.entries(bounds).forEach(([key, value]) => {
        params.set(key.replace(/[A-Z]/g, (letter) => `_${letter.toLowerCase()}`), value)
      })
    }
    const response = await fetch(`/api/v1/events?${params}`)
    const data = await response.json()
    if (!response.ok) throw new Error(data.detail || 'Каталог временно недоступен')
    events.value = data.items
  } catch (cause) {
    error.value = cause.message
    events.value = []
  } finally {
    loading.value = false
  }
}

async function choose(country) {
  selectedCountry.value = country
  modal.value = true
  await load(country.bounds)
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
    const params = new URLSearchParams({
      latitude: event.latitude,
      longitude: event.longitude,
      at: event.time,
      radius_km: '1500',
      limit: '12',
    })
    const response = await fetch(`/api/v1/stations/nearby?${params}`)
    const data = await response.json()
    if (!response.ok) throw new Error(data.detail || 'Не удалось получить станции')
    stations.value = data.items
  } catch (cause) {
    analysisError.value = cause.message
  } finally {
    stationLoading.value = false
  }
}

function toggleStation(station) {
  const key = `${station.network}.${station.station}`
  if (selectedStations.value.includes(key)) {
    selectedStations.value = selectedStations.value.filter((value) => value !== key)
  } else if (selectedStations.value.length < 5) {
    selectedStations.value = [...selectedStations.value, key]
  }
}

async function startAnalysis() {
  analysisError.value = ''
  try {
    const chosen = stations.value.filter((station) =>
      selectedStations.value.includes(`${station.network}.${station.station}`),
    )
    const response = await fetch('/api/v1/analyses', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ event: activeEvent.value, stations: chosen, ...analysisOptions.value }),
    })
    const data = await response.json()
    if (!response.ok) {
      throw new Error(typeof data.detail === 'string' ? data.detail : 'Проверьте параметры анализа')
    }
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
      if (!response.ok) throw new Error(data.detail || 'Не удалось получить результат')
      analysisJob.value = data
      if (['succeeded', 'failed'].includes(data.status)) return
    } catch (cause) {
      analysisError.value = cause.message
      return
    }
  }
  analysisError.value = 'Обработка длится дольше обычного. Повторите запрос позже.'
}

function tracePoints(trace) {
  const values = trace.series.values
  if (!values.length) return ''
  const windowStart = new Date(activeEvent.value.time).getTime() - plotOptions.value.seconds_before * 1000
  const windowDuration = (plotOptions.value.seconds_before + plotOptions.value.seconds_after) * 1000
  const traceStart = new Date(trace.start_time).getTime()
  const amplitudeScale = trace.series.normalized ? 1 : plotPeak.value
  return values.map((value, index) => {
    const x = ((traceStart - windowStart + index * trace.series.step_seconds * 1000) / windowDuration) * 700
    return `${x},${55 - (value / amplitudeScale) * 43}`
  }).join(' ')
}

const originX = computed(() => (
  (plotOptions.value.seconds_before / (plotOptions.value.seconds_before + plotOptions.value.seconds_after)) * 700
))

onMounted(load)
</script>

<template>
  <main>
    <header>
      <button class="brand" @click="page = 'overview'">SEISMO<span>SCOPE</span></button>
      <p>Каталог сейсмических событий · USGS FDSN Event API</p>
      <small>● данные через API</small>
    </header>

    <section v-if="page === 'overview'" class="layout">
      <aside>
        <em>РЕЖИМ НАБЛЮДЕНИЯ</em>
        <h1>Сейсмическая<br />картина мира</h1>
        <p>Укажите период и магнитуду. Выберите событие из каталога или нажмите на страну для сводки.</p>
        <hr />
        <b>Как читать карту</b>
        <p class="minor">Терракотовые точки — эпицентры. Размер точки соответствует магнитуде.</p>
      </aside>

      <section class="content">
        <form @submit.prevent="load(selectedCountry?.bounds)">
          <label>Начало<input v-model="filters.start" type="datetime-local" required /></label>
          <label>Конец<input v-model="filters.end" type="datetime-local" required /></label>
          <label>Магнитуда от<input v-model="filters.magnitude" type="number" min="0" max="10" step=".1" /></label>
          <button :disabled="loading">{{ loading ? 'Загрузка…' : 'Обновить карту' }}</button>
        </form>
        <p v-if="error" class="error">{{ error }}</p>
        <div class="heading">
          <div>
            <em>ИНТЕРАКТИВНАЯ КАРТА</em>
            <h2>Эпицентры и страны</h2>
          </div>
          <dl>
            <div><dt>Событий</dt><dd>{{ events.length }}</dd></div>
            <div><dt>Макс.</dt><dd>{{ largest ? `M ${largest.toFixed(1)}` : '—' }}</dd></div>
          </dl>
        </div>
        <WorldMap :events="events" :active-country-id="selectedCountry?.id" @select-country="choose" />
        <p class="note">Кликните по стране, чтобы открыть краткую сейсмическую сводку.</p>
        <div class="catalog-heading">
          <div><em>КАТАЛОГ СОБЫТИЙ</em><h2>Выберите событие для анализа</h2></div>
          <span>{{ loading ? 'Загрузка…' : `${events.length} найдено` }}</span>
        </div>
        <p v-if="!loading && !events.length" class="empty">За выбранный период событий не найдено.</p>
        <button v-for="event in events" :key="event.id" class="event-choice" @click="inspectEvent(event)">
          <b>M {{ event.magnitude?.toFixed(1) ?? '—' }}</b>
          <span>{{ event.place }}<small>{{ new Date(event.time).toLocaleString('ru-RU', { timeZone: 'UTC' }) }} UTC</small></span>
          <i>{{ event.depth_km ?? '—' }} км →</i>
        </button>
      </section>
    </section>

    <section v-else-if="page === 'detail'" class="detail">
      <button class="back" @click="page = 'overview'">← К карте</button>
      <em>СТРАНОВАЯ СВОДКА</em>
      <h1>{{ selectedCountry?.name }}</h1>
      <p>События магнитудой от {{ filters.magnitude }} за выбранный период.</p>
      <div class="stats">
        <div><span>Найдено</span><strong>{{ events.length }}</strong><small>событий</small></div>
        <div><span>Максимум</span><strong>{{ largest ? `M ${largest.toFixed(1)}` : '—' }}</strong><small>за период</small></div>
        <div><span>Источник</span><strong>USGS</strong><small>FDSN Event API</small></div>
      </div>
      <h2>Выберите событие</h2>
      <div v-if="!events.length" class="empty">Для выбранных параметров событий не найдено.</div>
      <button v-for="event in events" :key="event.id" class="event-choice" @click="inspectEvent(event)">
        <b>M {{ event.magnitude?.toFixed(1) ?? '—' }}</b>
        <span>{{ event.place }}<small>{{ new Date(event.time).toLocaleString('ru-RU', { timeZone: 'UTC' }) }} UTC</small></span>
        <i>{{ event.depth_km ?? '—' }} км →</i>
      </button>
    </section>

    <section v-else class="detail event-detail">
      <button class="back" @click="page = eventReturnPage">← К событиям</button>
      <em>АНАЛИЗ СОБЫТИЯ</em>
      <h1>{{ activeEvent?.place }}</h1>
      <p>{{ new Date(activeEvent?.time).toLocaleString('ru-RU', { timeZone: 'UTC' }) }} UTC · M {{ activeEvent?.magnitude }} · глубина {{ activeEvent?.depth_km }} км</p>
      <h2>Ближайшие станции</h2>
      <p>Выберите до пяти станций для одного события. Источник записей: EarthScope FDSN.</p>
      <p v-if="stationLoading">Ищем станции…</p>
      <p v-else-if="!stations.length">Станции не найдены в радиусе 1500 км.</p>
      <div class="station-list">
        <label v-for="station in stations" :key="`${station.network}.${station.station}`" class="station-option">
          <input type="checkbox" :checked="selectedStations.includes(`${station.network}.${station.station}`)" :disabled="selectedStations.length >= 5 && !selectedStations.includes(`${station.network}.${station.station}`)" @change="toggleStation(station)" />
          <b>{{ station.network }}.{{ station.station }}</b>
          <span>{{ station.site_name }}</span>
          <small>{{ station.distance_km }} км</small>
        </label>
      </div>
      <h2>Параметры обработки</h2>
      <div class="analysis-controls">
        <label>Канал<input v-model="analysisOptions.channel" maxlength="3" /></label>
        <label>До события, с<input v-model.number="analysisOptions.seconds_before" type="number" min="10" max="600" /></label>
        <label>После, с<input v-model.number="analysisOptions.seconds_after" type="number" min="30" max="1800" /></label>
        <label>Фильтр от, Гц<input v-model.number="analysisOptions.filter_low_hz" type="number" step=".1" min=".1" /></label>
        <label>Фильтр до, Гц<input v-model.number="analysisOptions.filter_high_hz" type="number" step=".1" min=".2" /></label>
        <label class="normalize"><input v-model="analysisOptions.normalize" type="checkbox" /> Нормировать графики</label>
      </div>
      <button class="more" :disabled="!selectedStations.length || ['pending', 'running'].includes(analysisJob?.status)" @click="startAnalysis">Загрузить и сравнить записи</button>
      <p v-if="analysisError" class="error">{{ analysisError }}</p>
      <p v-if="analysisJob" class="job-status">Задача: {{ jobLabels[analysisJob.status] ?? analysisJob.status }} <span v-if="analysisJob.error">· {{ analysisJob.error }}</span></p>
      <section v-if="analysisJob?.traces?.length" class="traces">
        <h2>Сравнение сигналов</h2>
        <p>Общая временная шкала: отметка события показана вертикальной линией. Без нормировки амплитудная шкала тоже общая. Оценка прихода приблизительная.</p>
        <div v-for="trace in analysisJob.traces" :key="trace.station" class="trace">
          <div class="trace-head">
            <b>{{ trace.station }} · {{ trace.channel }}</b>
            <span>пик {{ trace.metrics.peak_amplitude_counts }} · SNR {{ trace.metrics.snr_db ?? '—' }} dB · приход от события {{ trace.metrics.arrival_from_origin_seconds ?? '—' }} c</span>
          </div>
          <svg viewBox="0 0 700 110" preserveAspectRatio="none" :aria-label="`Сейсмограмма ${trace.station}`" role="img">
            <line x1="0" y1="55" x2="700" y2="55" />
            <line class="origin-line" :x1="originX" y1="0" :x2="originX" y2="110" />
            <polyline :points="tracePoints(trace)" />
          </svg>
          <small>Начало {{ trace.start_time }} · длительность {{ trace.metrics.duration_seconds }} c · шаг {{ trace.series.step_seconds.toFixed(3) }} c</small>
        </div>
      </section>
    </section>

    <div v-if="modal" class="veil" @click.self="modal = false">
      <section class="modal" role="dialog" aria-modal="true" :aria-label="`Сводка: ${selectedCountry?.name}`" @keydown.esc="modal = false">
        <button class="x" aria-label="Закрыть" @click="modal = false">×</button>
        <em>СТРАНА ВЫБРАНА</em>
        <h2>{{ selectedCountry?.name }}</h2>
        <p>Сводка событий в выбранной географической области.</p>
        <div class="modalstats">
          <span>Событий<strong>{{ loading ? '…' : events.length }}</strong></span>
          <span>Максимум<strong>{{ loading ? '…' : (largest ? `M ${largest.toFixed(1)}` : '—') }}</strong></span>
        </div>
        <button class="more" :disabled="loading" @click="modal = false; page = 'detail'">Подробнее о стране →</button>
      </section>
    </div>
  </main>
</template>
