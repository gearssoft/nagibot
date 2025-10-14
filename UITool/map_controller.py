"""
filename: map_controller.py
author: gbox3d

지도 표시 및 관리를 위한 컨트롤러
"""
from PySide6.QtCore import QObject, Qt
from PySide6.QtWebEngineWidgets import QWebEngineView
from my_qt_utils import match_widget_to_parent


class MapController(QObject):
    """지도 표시 및 관리 컨트롤러"""
    
    def __init__(self):
        super().__init__()
        self.web_view = None
        
    def initialize_map(self, parent_widget, label_widget, latitude=35.7299, longitude=126.5833, zoom=13):
        """
        OpenStreetMap 초기화
        
        Args:
            parent_widget: 지도를 표시할 부모 위젯
            label_widget: 준비 중 메시지를 표시할 레이블
            latitude: 초기 위도 (기본값: 부안 앞바다)
            longitude: 초기 경도 (기본값: 부안 앞바다)
            zoom: 줌 레벨 (기본값: 13)
        """
        # 준비 중 메시지 표시
        label_widget.setText("지도 준비 중")
        match_widget_to_parent(label_widget)
        label_widget.setAlignment(Qt.AlignCenter)
        
        # OpenStreetMap URL 설정
        map_url = f"https://www.openstreetmap.org/#map={zoom}/{latitude}/{longitude}"
        
        # QWebEngineView 생성 및 URL 로드
        self.web_view = QWebEngineView(parent_widget)
        self.web_view.setUrl(map_url)
        
        # 맨 뒤로 보내기
        self.web_view.lower()
        label_widget.lower()
        
        match_widget_to_parent(self.web_view)
        
        print(f"Map initialized: {map_url}")
    
    def update_location(self, latitude, longitude, zoom=None):
        """
        지도 위치 업데이트
        
        Args:
            latitude: 새로운 위도
            longitude: 새로운 경도
            zoom: 새로운 줌 레벨 (선택사항)
        """
        if not self.web_view:
            print("MapController: web_view not initialized")
            return
        
        if zoom is None:
            # 현재 줌 레벨 유지
            map_url = f"https://www.openstreetmap.org/#map=/{latitude}/{longitude}"
        else:
            map_url = f"https://www.openstreetmap.org/#map={zoom}/{latitude}/{longitude}"
        
        self.web_view.setUrl(map_url)
        print(f"Map location updated: {latitude}, {longitude}")
    
    def set_zoom(self, zoom_level):
        """
        줌 레벨 설정
        
        Args:
            zoom_level: 줌 레벨 (1-20)
        """
        if not self.web_view:
            print("MapController: web_view not initialized")
            return
        
        # 현재 URL에서 위도/경도 추출 후 새 줌 레벨로 업데이트
        # 간단히 JavaScript로 줌 조정
        js_code = f"map.setZoom({zoom_level});"
        self.web_view.page().runJavaScript(js_code)
    
    def cleanup(self):
        """리소스 정리"""
        if self.web_view:
            self.web_view.close()
            self.web_view = None
