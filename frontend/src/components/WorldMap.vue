<script setup>
import { computed, onMounted, ref } from 'vue'
import { feature } from 'topojson-client'
import { geoBounds, geoNaturalEarth1, geoPath } from 'd3-geo'
import world from 'world-atlas/countries-110m.json'

const props = defineProps({
  events: { type: Array, default: () => [] },
  activeCountryId: { type: [String, Number], default: null },
  activeEventId: { type: String, default: null },
})
const emit = defineEmits(['select-country', 'select-event'])
const projection = geoNaturalEarth1().translate([510, 270]).scale(175)
const path = geoPath(projection)
const countries = feature(world, world.objects.countries).features
const hoveredEvent = ref(null)
const boundaries = ref([])
const countryPaths = computed(() => countries.map((country) => ({ ...country, d: path(country) })))
const markers = computed(() => props.events.map((event) => ({ ...event, point: projection([event.longitude, event.latitude]) })).filter((event) => event.point))
const boundaryPaths = computed(() => boundaries.value.map((boundary) => ({ ...boundary, d: path(boundary), type: boundary.properties?.LABEL || 'Other Boundary' })))

function selectCountry(country) {
  const [[minLongitude, minLatitude], [maxLongitude, maxLatitude]] = geoBounds(country)
  emit('select-country', { id: country.id, name: country.properties?.name || 'Страна ' + country.id, bounds: { minLatitude, maxLatitude, minLongitude, maxLongitude } })
}

function eventLabel(event) {
  const magnitude = event.magnitude === null || event.magnitude === undefined ? 'не указана' : 'M ' + event.magnitude.toFixed(1)
  return magnitude + ', ' + (event.place || 'место не указано')
}

onMounted(async () => {
  try {
    const response = await fetch('/api/v1/layers/plate-boundaries')
    if (response.ok) boundaries.value = (await response.json()).features
  } catch {
    boundaries.value = []
  }
})
</script>

<template>
  <div class="map-shell">
    <svg viewBox="0 0 1020 540" class="world-map" role="img" aria-label="Карта мира с эпицентрами землетрясений и границами тектонических плит">
      <rect width="1020" height="540" class="ocean" />
      <path v-for="country in countryPaths" :key="country.id" :d="country.d" :class="['country-shape', { active: String(activeCountryId) === String(country.id) }]" tabindex="0" role="button" :aria-label="'Показать сводку: ' + (country.properties?.name || 'страна')" @click="selectCountry(country)" @keydown.enter.prevent="selectCountry(country)" @keydown.space.prevent="selectCountry(country)" />
      <path v-for="(boundary, index) in boundaryPaths" :key="index" :d="boundary.d" :class="['boundary', boundary.type.includes('Convergent') ? 'convergent' : boundary.type.includes('Divergent') ? 'divergent' : 'transform']" />
      <g v-for="event in markers" :key="event.id" :transform="'translate(' + event.point[0] + ',' + event.point[1] + ')'" :class="['event-marker', { active: activeEventId === event.id }]" tabindex="0" role="button" :aria-label="'Открыть анализ: ' + eventLabel(event)" @mouseenter="hoveredEvent = event" @mouseleave="hoveredEvent = null" @focus="hoveredEvent = event" @blur="hoveredEvent = null" @click="emit('select-event', event)" @keydown.enter.prevent="emit('select-event', event)" @keydown.space.prevent="emit('select-event', event)">
        <circle :r="3 + Math.min((event.magnitude || 1) * 0.9, 6)" /><circle r="1.3" />
      </g>
      <g v-if="hoveredEvent" class="map-tooltip" :transform="'translate(' + Math.min(hoveredEvent.point[0] + 12, 775) + ',' + Math.max(hoveredEvent.point[1] - 36, 28) + ')'">
        <rect width="230" height="48" /><text x="10" y="18">M {{ hoveredEvent.magnitude?.toFixed(1) ?? '—' }} · {{ hoveredEvent.depth_km ?? '—' }} км</text><text x="10" y="35">{{ hoveredEvent.place }}</text>
      </g>
    </svg>
    <div class="map-legend" aria-label="Легенда карты"><span><i class="event-dot"></i>Эпицентр</span><span><i class="conv"></i>Схождение плит</span><span><i class="div"></i>Расхождение</span><span><i class="trans"></i>Сдвиг</span></div>
  </div>
</template>

<style scoped>
.map-shell{position:relative;background:#d9e5e3;border:1px solid #adc4c0}.world-map{display:block;width:100%;height:auto;min-height:430px}.ocean{fill:#d9e5e3}.country-shape{fill:#f7f4ed;stroke:#99b5b0;stroke-width:.55;cursor:pointer;transition:fill .12s,stroke .12s}.country-shape:hover,.country-shape:focus{fill:#dce9df;stroke:#356d68;outline:none}.country-shape.active{fill:#b5d2c2;stroke:#174f4b;stroke-width:1.2}.boundary{fill:none;stroke-width:1.2;pointer-events:none}.convergent{stroke:#a44937}.divergent{stroke:#2e7483}.transform{stroke:#7e657d;stroke-dasharray:3 2}.event-marker{cursor:pointer;outline:none}.event-marker circle:first-child{fill:#bd5338;stroke:#fffaf1;stroke-width:1.2;opacity:.96;transition:fill .12s,stroke-width .12s}.event-marker circle:last-child{fill:#5a2018}.event-marker:hover circle:first-child,.event-marker:focus circle:first-child,.event-marker.active circle:first-child{fill:#8d321f;stroke-width:2.2}.map-tooltip{pointer-events:none}.map-tooltip rect{fill:#173f3c;stroke:#f7f4ed;stroke-width:1}.map-tooltip text{fill:#fffaf1;font:11px 'IBM Plex Sans',sans-serif}.map-tooltip text:last-child{font-size:10px}.map-legend{position:absolute;left:14px;bottom:14px;display:flex;flex-wrap:wrap;gap:8px 14px;padding:8px 10px;background:#fffaf1e8;border:1px solid #b8cbc7;color:#314e4b;font:10px 'IBM Plex Sans',sans-serif}.map-legend span{display:flex;gap:5px;align-items:center}.map-legend i{display:inline-block;width:13px;height:3px}.event-dot{width:8px!important;height:8px!important;border-radius:50%;background:#bd5338}.conv{background:#a44937}.div{background:#2e7483}.trans{background:repeating-linear-gradient(90deg,#7e657d 0 3px,transparent 3px 5px)}@media(max-width:600px){.world-map{min-height:260px}.map-legend{left:8px;right:8px;bottom:8px;gap:5px 10px;font-size:9px}.map-tooltip{display:none}}
</style>
