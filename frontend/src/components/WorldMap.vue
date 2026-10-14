<script setup>
import { computed, onMounted, ref } from 'vue'
import { feature } from 'topojson-client'
import { geoBounds, geoNaturalEarth1, geoPath } from 'd3-geo'
import world from 'world-atlas/countries-110m.json'
const props = defineProps({ events: { type: Array, default: () => [] }, activeCountryId: { type: [String, Number], default: null } })
const emit = defineEmits(['select-country'])
const projection = geoNaturalEarth1().translate([510, 270]).scale(175)
const path = geoPath(projection)
const countries = feature(world, world.objects.countries).features
const countryPaths = computed(() => countries.map((country) => ({ ...country, d: path(country) })))
const markers = computed(() => props.events.map((event) => ({ ...event, point: projection([event.longitude, event.latitude]) })).filter((event) => event.point))
const boundaries = ref([])
const boundaryPaths = computed(() => boundaries.value.map((boundary) => ({ ...boundary, d: path(boundary), type: boundary.properties?.LABEL || 'Other Boundary' })))
function select(country) { const [[minLongitude, minLatitude], [maxLongitude, maxLatitude]] = geoBounds(country); emit('select-country', { id: country.id, name: country.properties?.name || `Страна ${country.id}`, bounds: { minLatitude, maxLatitude, minLongitude, maxLongitude } }) }
onMounted(async () => { try { const response = await fetch('/api/v1/layers/plate-boundaries'); if (response.ok) boundaries.value = (await response.json()).features } catch { boundaries.value = [] } })
</script>
<template><div class="map-shell"><svg viewBox="0 0 1020 540" class="world-map" role="img" aria-label="Карта мира: нажмите на страну для просмотра сейсмической сводки"><rect width="1020" height="540" fill="#dce9e8"/><path v-for="country in countryPaths" :key="country.id" :d="country.d" :class="['country-shape', { active: String(activeCountryId) === String(country.id) }]" @click="select(country)"/><path v-for="(boundary, index) in boundaryPaths" :key="index" :d="boundary.d" :class="['boundary', boundary.type.includes('Convergent') ? 'convergent' : boundary.type.includes('Divergent') ? 'divergent' : 'transform']"/><g v-for="event in markers" :key="event.id" :transform="`translate(${event.point[0]},${event.point[1]})`" class="event-marker"><circle :r="3 + Math.min((event.magnitude || 1) * .9, 6)"/><circle r="1.4"/></g></svg><div class="map-legend"><span><i class="event-dot"></i> эпицентр</span><span><i class="conv"></i> схождение плит</span><span><i class="div"></i> расхождение</span><span><i class="trans"></i> сдвиг</span></div></div></template>
<style scoped>.map-shell{position:relative;border:1px solid #b7cbc9;background:#dce9e8}.world-map{display:block;width:100%;height:auto;min-height:390px}.country-shape{fill:#f7f5ef;stroke:#9bb5b4;stroke-width:.55;cursor:pointer;transition:fill .14s}.country-shape:hover{fill:#d4e4dd}.country-shape.active{fill:#9acbb9;stroke:#155b58;stroke-width:1.2}.boundary{fill:none;stroke-width:1.25;pointer-events:none}.convergent{stroke:#9e4136}.divergent{stroke:#286e89}.transform{stroke:#765a83;stroke-dasharray:3 2}.event-marker circle:first-child{fill:#c55f3d;stroke:#fff8ef;stroke-width:1.2;opacity:.95}.event-marker circle:last-child{fill:#5d1e16}.map-legend{position:absolute;bottom:13px;left:16px;display:flex;gap:13px;padding:7px 9px;background:#fffdf8e8;border:1px solid #c7d6d4;color:#385150;font-size:10px}.map-legend span{display:flex;gap:5px;align-items:center}.map-legend i{display:inline-block;width:12px;height:3px}.event-dot{width:8px!important;height:8px!important;border-radius:50%;background:#c55f3d}.conv{background:#9e4136}.div{background:#286e89}.trans{background:repeating-linear-gradient(90deg,#765a83 0 3px,transparent 3px 5px)}</style>
