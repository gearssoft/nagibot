# map_controller.py
from PySide6.QtCore import QObject, Qt, QTimer, QEvent, Signal, Slot
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebChannel import QWebChannel
from my_qt_utils import match_widget_to_parent

_LEAFLET_HTML = r"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Robot Map</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <link
    rel="stylesheet"
    href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
    integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY="
    crossorigin=""
  />
  <style>
    html, body, #map { height: 100%; margin: 0; padding: 0; }

    /* 로봇 헤딩 아이콘 (DivIcon) */
    .robot-wrap {
      position: relative;
      width: 36px; height: 36px;
      transform: translate(-18px, -18px); /* 마커 기준점을 중앙으로 */
    }

    .robot-arrow {
        position: absolute;
        left: 50%; top: 50%;
        width: 0; height: 0;
        transform-origin: 50% 50%;
        /* 위쪽을 향하는 삼각형(기본 0deg = 북쪽) */
        border-left: 8px solid transparent;
        border-right: 8px solid transparent;
        border-bottom: 28px solid #0078ff;   /* 높이 ↑ */
        transform: translate(-50%, -70%) rotate(0deg);  /* 약간 위로 밀기 */
        filter: drop-shadow(0 1px 2px rgba(0,0,0,0.35));
    }

    .robot-core {
      position: absolute;
      left: 50%; top: 50%;
      width: 10px; height: 10px;
      transform: translate(-50%, -50%);
      background: white;
      border: 2px solid #0078ff;
      border-radius: 50%;
      box-shadow: 0 0 4px rgba(0,0,0,.35);
    }
  </style>
</head>
<body>
  <div id="map"></div>

    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
            integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" crossorigin=""></script>
    <script src="qrc:///qtwebchannel/qwebchannel.js"></script>

    <script>

    function cssAngleFromHeading(headingDeg) {
    // 로봇 yaw 0°=동(East), CCW+, CSS는 CW+ → 변환
    // CSS 각도 = 90 - headingDeg
    const h = (headingDeg || 0);
    return 90 - h;
    }

    let map, robotMarker, pyBridge = null;   /* ✅ 중복 선언 금지: 한 번만 */

    function makeRobotIcon(headingDeg) {
        const html =
        '<div class="robot-wrap">' +
            '<div class="robot-arrow" style="transform: translate(-50%, -60%) rotate(' + cssAngleFromHeading(headingDeg) + 'deg)"></div>' +
            '<div class="robot-core"></div>' +
        '</div>';
        return L.divIcon({
        html,
        className: '',
        iconSize: [36, 36],
        iconAnchor: [18, 18],
        });
    }

    // WebChannel 연결
    if (typeof qt !== "undefined") {
        new QWebChannel(qt.webChannelTransport, function (channel) {
        pyBridge = channel.objects.pyBridge;
        });
    }

    function initMap(lat, lon, zoom) {
        map = L.map('map').setView([lat, lon], zoom);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 20, attribution: '&copy; OpenStreetMap'
        }).addTo(map);

        // 드래그/줌 시작/종료 시 Python에 알림
        const onStart = () => { if (pyBridge) pyBridge.onDrag(true); };
        const onEnd   = () => { if (pyBridge) pyBridge.onDrag(false); };
        map.on('movestart', onStart);
        map.on('dragstart', onStart);
        map.on('zoomstart', onStart);
        map.on('moveend', onEnd);
        map.on('dragend', onEnd);
        map.on('zoomend', onEnd);
    }

    // headingDeg: degrees (0°=북, +시계방향)
    function updateRobot(lat, lon, headingDeg, center=true) {
        if (!map) return;
        const pos = [lat, lon];
        if (!robotMarker) {
        robotMarker = L.marker(pos, { icon: makeRobotIcon(headingDeg) }).addTo(map);
        } else {
        robotMarker.setLatLng(pos);
        robotMarker.setIcon(makeRobotIcon(headingDeg));
        }
        if (center) {
        map.setView(pos, map.getZoom(), { animate: false });
        }
    }

    /* 전역 바인딩(중요) */
    window.initMap = initMap;
    window.updateRobot = updateRobot;
</script>


  
</body>
</html>
"""

# JS → Python 브릿지
class _MapBridge(QObject):
    dragChanged = Signal(bool)

    @Slot(bool)
    def onDrag(self, is_drag: bool):
        # JS에서 넘어온 드래그 상태를 그대로 신호로
        self.dragChanged.emit(bool(is_drag))

class MapController(QObject):

    dragChanged = Signal(bool)  # ← 추가: 드래그 상태 변경 알림

    def __init__(self):
        super().__init__()
        self.web_view = None
        self._inited = False
        self._pending = None   # (lat, lon, headingDeg, center)
        
        

        self._dragging = False
        self._drag_cooldown = QTimer(self)
        self._drag_cooldown.setSingleShot(True)
        self._drag_cooldown.setInterval(600)  # 입력 멈춘 뒤 0.6초 후 drag=False


        self._channel = None
        self._bridge = None

        self._drag_cooldown.timeout.connect(self._clear_drag)

    def _set_drag(self, on: bool):
        if self._dragging != on:
            self._dragging = on
            self.dragChanged.emit(on)  # MainForm으로 알림

    def _clear_drag(self):
        self._set_drag(False)

    def isReady(self):
        return self.web_view is not None and self._inited

    def initialize_map(self, parent_widget, label_widget,
                       latitude=35.7299, longitude=126.5833, zoom=13):
        label_widget.setText("지도 준비 중")
        match_widget_to_parent(label_widget)
        label_widget.setAlignment(Qt.AlignCenter)

        self.web_view = QWebEngineView(parent_widget)
        self.web_view.setHtml(_LEAFLET_HTML)
        
        # WebChannel: JS와 통신 세팅
        self._channel = QWebChannel(self.web_view.page())
        self._bridge = _MapBridge()
        self._channel.registerObject("pyBridge", self._bridge)
        self.web_view.page().setWebChannel(self._channel)

        # JS → Python dragChanged를 MapController.dragChanged로 중계
        self._bridge.dragChanged.connect(lambda v: (self._set_drag(v)))

        self.web_view.lower()
        label_widget.lower()
        match_widget_to_parent(self.web_view)

        def _after_load_ok(_=None):
            self.web_view.page().runJavaScript(f"initMap({latitude}, {longitude}, {zoom});")

            self._inited = True
            if self._pending is not None:
                plat, plon, phead, pcenter = self._pending
                self._pending = None
                js = f"updateRobot({float(plat)}, {float(plon)}, {float(phead)}, {str(bool(pcenter)).lower()});"
                QTimer.singleShot(0, lambda: self.web_view.page().runJavaScript(js))


        self.web_view.page().loadFinished.connect(_after_load_ok)

    def update_robot_marker(self, latitude, longitude, heading_deg=0.0, center=True):
        if not (self.web_view and self._inited):
            print("MapController: not ready yet")
            self._pending = (latitude, longitude, heading_deg, center)
            return
        lat = float(latitude); lon = float(longitude)
        head = float(heading_deg); ctr = bool(center)
        js = f"updateRobot({lat}, {lon}, {head}, {str(ctr).lower()});"
        QTimer.singleShot(0, lambda: self.web_view.page().runJavaScript(js))

    def cleanup(self):
        if self.web_view:
            self.web_view.close()
            self.web_view = None
            self._inited = False
            self._pending = None
