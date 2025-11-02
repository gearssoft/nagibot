// filename: www/mapView.js
// 이주석은 지우지 하세요.

import * as L from "https://unpkg.com/leaflet@1.9.4/dist/leaflet-src.esm.js";
import { getMetadataByKey } from "./apiHelper.js";

// --- 모듈 내부 상태 ---
let _leaflet = {
  map: null,
  layers: {
    base: null,
    marker: null,
    accuracy: null,
  },
};

/**
 * 지도 초기화 (중복 생성 방지)
 * @param {Object} opts
 * @param {number[]} opts.center [lat, lng]
 * @param {number} opts.zoom
 */
export async function initMap(opts = {}) {
  if (_leaflet.map) return _leaflet.map;

  const center = Array.isArray(opts.center) ? opts.center : [37.5665, 126.9780]; // 서울
  const zoom = Number.isFinite(opts.zoom) ? opts.zoom : 13;

  _leaflet.map = L.map("map-frame").setView(center, zoom);
  _leaflet.layers.base = L.tileLayer(
    "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    {
      maxZoom: 19,
      attribution: "&copy; OpenStreetMap contributors",
    }
  ).addTo(_leaflet.map);

  return _leaflet.map;
}

/**
 * 현재 마커를 주어진 좌표로 렌더/업데이트
 * @param {number} lat
 * @param {number} lng
 * @param {number|null} acc  정확도 반경(m) (선택)
 */
export function setMarkerByLatLng(lat, lng, acc = null) {
  if (!_leaflet.map) return;

  // 기존 레이어 제거
  if (_leaflet.layers.marker) {
    _leaflet.map.removeLayer(_leaflet.layers.marker);
    _leaflet.layers.marker = null;
  }
  if (_leaflet.layers.accuracy) {
    _leaflet.map.removeLayer(_leaflet.layers.accuracy);
    _leaflet.layers.accuracy = null;
  }

  // 새 마커
  _leaflet.layers.marker = L.marker([lat, lng]).addTo(_leaflet.map);

  // 정확도 반경 표시
  if (typeof acc === "number" && isFinite(acc) && acc > 0) {
    _leaflet.layers.accuracy = L.circle([lat, lng], { radius: acc }).addTo(_leaflet.map);
  }

  // 보기 좋게 이동
  _leaflet.map.setView([lat, lng], Math.max(_leaflet.map.getZoom(), 15));
}

/**
 * 메타데이터에서 좌표를 가져옴
 * 우선순위:
 *   A) robot_{n}.position = {lat, lng, acc?}
 *   B) robot_{n}.lat / robot_{n}.lng
 * @param {number} unitIndex  1호기=1, 2호기=2, 3호기=3 ...
 * @returns {Promise<{lat:number,lng:number,acc:number|null}|null>}
 */
export async function getUnitLatLngFromMetadata(unitIndex) {
  const i = unitIndex;

  // A) position 객체 탐색
  try {
    const resPos = await getMetadataByKey(`robot_${i}.position`);
    if (resPos?.r === "ok" && resPos?.value && typeof resPos.value === "object") {
      const { lat, lng, acc } = resPos.value;
      if (typeof lat === "number" && typeof lng === "number") {
        return { lat, lng, acc: (typeof acc === "number" ? acc : null) };
      }
    }
  } catch (_) {}

  // B) 개별 lat/lng 탐색
  try {
    const [resLat, resLng] = await Promise.all([
      getMetadataByKey(`robot_${i}.lat`),
      getMetadataByKey(`robot_${i}.lng`),
    ]);
    const lat = resLat?.r === "ok" ? resLat.value : null;
    const lng = resLng?.r === "ok" ? resLng.value : null;
    if (typeof lat === "number" && typeof lng === "number") {
      return { lat, lng, acc: null };
    }
  } catch (_) {}

  return null;
}

/**
 * 선택된 호기 기준으로 지도 갱신
 * @param {number} unitIndex 1,2,3...
 */
export async function updateMapForCurrentUnit(unitIndex) {
  if (!_leaflet.map) await initMap();
  const pos = await getUnitLatLngFromMetadata(unitIndex);
  if (!pos) {
    console.warn("[mapView] 좌표 정보 없음:", unitIndex);
    return;
  }
  setMarkerByLatLng(pos.lat, pos.lng, pos.acc ?? null);
}

/** (선택) 지도 제거 */
export function destroyMap() {
  if (_leaflet.map) {
    _leaflet.map.remove();
    _leaflet = { map: null, layers: { base: null, marker: null, accuracy: null } };
  }
}
