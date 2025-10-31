"""
filename: MainForm.py
author: gbox3d

위 주석을 수정하지 마시오
"""
import sys
from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtCore import Signal, Slot,QTimer
from PySide6.QtGui import QFontDatabase

import UI.mainForm
from cssutils import change_background_color, change_text_color
from my_qt_utils import match_widget_to_parent
from configMng import ConfigManager
# from robot_client import RobotClient

# 리팩토링된 컨트롤러 및 매니저 임포트
from video_controller import VideoController
from map_controller import MapController
from status_manager import StatusManager

from network_adapter import NetworkAdapter
from client.client import Client

class MainForm(QWidget, UI.mainForm.Ui_mainForm):
    
    gotoHomeSignal = Signal()
    gotoSetupSignal = Signal()
    closedSignal = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 설정 관리자 초기화
        self._initialize_config()
        
        # 폰트 초기화
        # self._initialize_font()
        
        # # UI 설정
        self.setupUi(self)

        # ===== NetworkAdapter 주입 =====
        def _factory():
            # 연결 파라미터를 한 곳에 모읍니다.
            return Client(host="localhost", port=8282)

        self.netMMS = NetworkAdapter(client_factory=_factory, parent=self)

        # 어댑터 시그널 구독 → UI 슬롯
        self.netMMS.connected.connect(self._ui_on_connected)
        self.netMMS.disconnected.connect(self._ui_on_disconnected)
        self.netMMS.error.connect(self._ui_on_error)
        self.netMMS.message.connect(self._ui_on_message)

        # 앱 종료 시 안전 정리
        QApplication.instance().aboutToQuit.connect(self.netMMS.shutdown)

        # 자동 연결 (원래 Connect_network에서 하던 동작)
        self.netMMS.start()
        #=======================================================================

        # === 추가: 메타데이터 주기 폴링 타이머 ===
        self._meta_interval_ms = 1000  # 기본 1초 (원하면 옵션화)
        self._meta_timer = QTimer(self)
        self._meta_timer.setInterval(self._meta_interval_ms)
        self._meta_timer.timeout.connect(self._poll_MMS_metadata)

        # === 추가: 하트비트 타이머(서버가 code=100 후 끊는 현상 방지) ===
        self._hb_interval_ms = 3000          # 서버 요건에 맞게 조정(예: 300~1000ms)
        self._hb_timer = QTimer(self)
        self._hb_timer.setInterval(self._hb_interval_ms)
        self._hb_timer.timeout.connect(self._send_heartbeat)


    
    # === 메타데이터 폴링 ===
    @Slot()
    def _poll_MMS_metadata(self):
        print("[UI] Polling MMS metadata...")

        unit_no = (getattr(self, "current_unit_index", 0) or 0) + 1
        key = f"robot_{unit_no}"
        print(f"[UI] Polling MMS metadata... key={key}")
        if getattr(self, "netMMS", None) and self.netMMS.is_connected():
            self.netMMS.fetch_json_by_key(key)   # ← 어댑터 래퍼 호출



    # === 하트비트 전송 ===
    @Slot()
    def _send_heartbeat(self):
        if getattr(self, "netMMS", None) and self.netMMS.is_connected():
            # self.netMMS.send_ping({"ts": self.netMMS.now_ts()})
            self.netMMS.ping_server()
            print("[UI] Sent heartbeat ping to MMS.")


    # ===== UI 슬롯 =====
    @Slot(dict)
    def _ui_on_connected(self, json_info: dict):

        self.label_connection_status.setText("Connected")
        self.label_connection_status.setStyleSheet("color: white;background-color: green;")

        if not self._meta_timer.isActive():
            self._meta_timer.start()
            print("[UI] Started MMS metadata polling timer.")

        if not self._hb_timer.isActive():
            self._hb_timer.start()
            print("[UI] Started heartbeat timer.")
        
                
        print("[UI] Connected:", json_info)

    @Slot(str)
    def _ui_on_disconnected(self, reason: str):
        print("[UI] Disconnected:", reason)        

    @Slot(str)
    def _ui_on_error(self, msg: str):
        print("[UI] Error:", msg)

    @Slot(dict)
    def _ui_on_message(self, payload: dict):
        print("[UI] Message:", payload)

        _robot_data = payload.get("data", {}).get("value", {})

        print(f"[UI] Received robot data: {_robot_data}")

        if _robot_data:
            mission_mode = _robot_data.get("mission_mode", "unknown")
            operation_mode = _robot_data.get("operation_mode", "unknown")

            self.rb_opmode_auto.setChecked(False)
            self.rb_opmode_operator.setChecked(False)
            self.rb_opmode_manual.setChecked(False)

            if operation_mode == "auto":
                self.rb_opmode_auto.setChecked(True)
            if operation_mode == "operator":
                self.rb_opmode_operator.setChecked(True)
            if operation_mode == "manual":
                self.rb_opmode_manual.setChecked(True)


            self.rb_ms_move.setChecked(False)
            self.rb_ms_patrol.setChecked(False)            
            self.rb_ms_tracking.setChecked(False)
            self.rb_ms_return.setChecked(False)
            self.rb_ms_stop.setChecked(False)
            

            if mission_mode == "move":
                self.rb_ms_move.setChecked(True)
            elif mission_mode == "patrol":
                self.rb_ms_patrol.setChecked(True)
            elif mission_mode == "tracking":
                self.rb_ms_tracking.setChecked(True)
            elif mission_mode == "return":
                self.rb_ms_return.setChecked(True)
            elif mission_mode == "stop":
                self.rb_ms_stop.setChecked(True)

    #===================== UI 초기화 ====================
    
    def _initialize_config(self):
        """설정 파일 로드 및 초기화"""
        self.configMng = ConfigManager()
        if not self.configMng.load_config():
            print("ConfigManager: 설정 파일 로드 실패")
            sys.exit(-1)
        
        print("ConfigManager: 설정 파일 로드 성공")
        
        self.current_unit_index = self.configMng.get_current_select_unit() - 1
        self.current_unit_index_sub = self.configMng.get_current_select_unit_sub() - 1
        
        print(f"ConfigManager: 현재 선택된 차량 인덱스: {self.current_unit_index}")
        print(f"ConfigManager: 현재 선택된 서브 차량 인덱스: {self.current_unit_index_sub}")       
    
    
    
    def _connect_signals(self):
        """버튼 시그널 연결"""
        # 네비게이션 버튼
        self.btnGoHome.clicked.connect(self.gotoHome)
        self.btnGotoSetup.clicked.connect(self.gotoSetup)
        
        # 방향키 버튼
        self.btnKeyUp.pressed.connect(self.keyUpPressed)
        self.btnKeyUp.released.connect(self.keyUpReleased)
        self.btnKeyDown.pressed.connect(self.keyDownPressed)
        self.btnKeyDown.released.connect(self.keyDownReleased)
        self.btnKeyLeft.pressed.connect(self.keyLeftPressed)
        self.btnKeyLeft.released.connect(self.keyLeftReleased)
        self.btnKeyRight.pressed.connect(self.keyRightPressed)
        self.btnKeyRight.released.connect(self.keyRightReleased)
        
        
    
    def _initialize_ui_state(self):
        """UI 초기 상태 설정"""
        # 키 버튼 표시 설정
        self._setup_key_button_visibility()
        
        # 배경색 설정
        self.checkColor = "#000000"
        self.checkBackgroundColor = "rgb(188, 215, 236)"
        self.defaultBackgroundColor = "#ffffff"
        self.defaultColor = "#000000"
        
        # 모드 버튼 초기 색상
        self._setup_mode_buttons()
        
        # 호기 표시
        self.txUnitNuberInfo.setText(f"{self.current_unit_index+1} 호기")
    
    def _setup_key_button_visibility(self):
        """키 버튼 레이블 표시 설정"""
        self.label_keyup_normal.setVisible(True)
        self.label_keyup_push.setVisible(False)
        self.label_keydown_normal.setVisible(True)
        self.label_keydown_push.setVisible(False)
        self.label_keyleft_normal.setVisible(True)
        self.label_keyleft_push.setVisible(False)
        self.label_keyright_normal.setVisible(True)
        self.label_keyright_push.setVisible(False)
    
    def _setup_mode_buttons(self):
        """모드 버튼 초기 색상 설정"""
        # 자율주행/원격주행
        change_background_color(self.btnAutoDrv, self.checkBackgroundColor)
        change_text_color(self.btnAutoDrv, self.checkColor)
        change_background_color(self.btnRemoteDrv, self.defaultBackgroundColor)
        change_text_color(self.btnRemoteDrv, self.defaultColor)
        
        # 광학/적외선
        change_background_color(self.btnOpticalMode, self.checkBackgroundColor)
        change_text_color(self.btnOpticalMode, self.checkColor)
        change_background_color(self.btnIRMode, self.defaultBackgroundColor)
        change_text_color(self.btnIRMode, self.defaultColor)
        
        # 스케일 업/다운
        change_background_color(self.btnScaleUp, self.checkBackgroundColor)
        change_text_color(self.btnScaleUp, self.checkColor)
        change_background_color(self.btnScaleDown, self.defaultBackgroundColor)
        change_text_color(self.btnScaleDown, self.defaultColor)
        
        # 잠금/해제
        change_background_color(self.labelUnLock, self.checkBackgroundColor)
        change_text_color(self.labelUnLock, self.checkColor)
        change_background_color(self.labelLock, self.defaultBackgroundColor)
        change_text_color(self.labelLock, self.defaultColor)
    
    def _initialize_controllers(self):
        """컨트롤러 및 매니저 초기화"""
        # 상태 관리자
        self.statusManager = StatusManager()
        
        # 비디오 컨트롤러
        self.videoController = VideoController(
            self.configMng,
            self.current_unit_index,
            self.current_unit_index_sub,
            self.font_d2coding
        )
        
        # 메인 카메라 초기화
        if self.videoController.initialize_main_camera(self.mainCamScreen_bmpLabel, self.mainCamScreen):
            # 비디오 스레드 시그널 연결
            self.videoController.mainCameraThread.change_pixmap_signal.connect(
                lambda img: self.videoController.update_main_image(
                    img, self.mainCamScreen_bmpLabel, self.mainCamScreen
                )
            )
            
            # 감지 서버 초기화
            if self.videoController.initialize_detection(self.edLogText):
                self.videoController.yolo_detection_thread.detection_results.connect(
                    lambda d, i: self.videoController.on_detection_results(d, i, self.edLogText)
                )
                self.videoController.yolo_detection_thread.status_update.connect(
                    lambda msg: self.videoController.on_detection_status(msg, self.edLogText)
                )
        
        # 서브 카메라 초기화
        if self.videoController.initialize_sub_camera(self.labelSubCamera):
            match_widget_to_parent(self.labelSubCamera)
            self.videoController.subCameraThread.change_pixmap_signal.connect(
                lambda img: self.videoController.update_sub_image(img, self.labelSubCamera)
            )
        
        # 지도 컨트롤러
        self.mapController = MapController()
        self.mapController.initialize_map(
            self.widgetBottomRightScreen,
            self.labelBottomRightScreen,
            latitude=35.7299,
            longitude=126.5833,
            zoom=13
        )
    
    
    # ==================== 타이머 콜백 ====================
    
    @Slot()
    def _update_clock(self):
        """시계 업데이트"""
        self.statusManager.update_clock_widgets(self.currentTime, self.operationTime)
    
    @Slot()
    def _update_status(self):
        """상태 업데이트"""
        self.statusManager.update_status_widgets(
            self.wifiStatus, self.networkStatus, self.batteryStatus,
            self.labelAreaName, self.labelWether, self.labelTemper,
            self.labelRain, self.labelWindy, self.labelHumidty,
            self.labelPrecipitation, self.labelWaveHeight,
            self.edLogText
        )
    
    @Slot()
    def gotoHome(self):
        print("gotoHome")
        self.gotoHomeSignal.emit()
    
    @Slot()
    def gotoSetup(self):
        print("gotoSetup")
        self.gotoSetupSignal.emit()
    
    # 방향키 버튼
    @Slot()
    def keyUpPressed(self):
        self.label_keyup_normal.setVisible(False)
        self.label_keyup_push.setVisible(True)
        if self.activeRobot:
            self.activeRobot.send_drive_command(1.0, 0.0)
    
    @Slot()
    def keyUpReleased(self):
        self.label_keyup_normal.setVisible(True)
        self.label_keyup_push.setVisible(False)
        if self.activeRobot:
            self.activeRobot.send_drive_command(0.0, 0.0)
    
    @Slot()
    def keyDownPressed(self):
        self.label_keydown_normal.setVisible(False)
        self.label_keydown_push.setVisible(True)
        if self.activeRobot:
            self.activeRobot.send_drive_command(-1.0, 0.0)
    
    @Slot()
    def keyDownReleased(self):
        self.label_keydown_normal.setVisible(True)
        self.label_keydown_push.setVisible(False)
        if self.activeRobot:
            self.activeRobot.send_drive_command(0.0, 0.0)
    
    @Slot()
    def keyLeftPressed(self):
        self.label_keyleft_normal.setVisible(False)
        self.label_keyleft_push.setVisible(True)
        if self.activeRobot:
            self.activeRobot.send_drive_command(0.5, 0.5)
    
    @Slot()
    def keyLeftReleased(self):
        self.label_keyleft_normal.setVisible(True)
        self.label_keyleft_push.setVisible(False)
        if self.activeRobot:
            self.activeRobot.send_drive_command(0.0, 0.0)
    
    @Slot()
    def keyRightPressed(self):
        self.label_keyright_normal.setVisible(False)
        self.label_keyright_push.setVisible(True)
        if self.activeRobot:
            self.activeRobot.send_drive_command(0.5, -0.5)
    
    @Slot()
    def keyRightReleased(self):
        self.label_keyright_normal.setVisible(True)
        self.label_keyright_push.setVisible(False)
        if self.activeRobot:
            self.activeRobot.send_drive_command(0.0, 0.0)
    
    # 비상정지 버튼
    @Slot()
    def btnAbnormalStopPressed(self):
        print("btnAbnormalStopPressed")
        change_background_color(self.btnAbnormalStop, '#FFFFFF')
        change_text_color(self.btnAbnormalStop, '#FF0000')
    
    @Slot()
    def btnAbnormalStopReleased(self):
        print("btnAbnormalStopReleased")
        change_background_color(self.btnAbnormalStop, '#FF0000')
        change_text_color(self.btnAbnormalStop, '#FFFFFF')
    
    @Slot()
    def btnAbnormalStopClicked(self):
        print("btnAbnormalStopClicked")
    
    # 모드 선택 버튼
    @Slot()
    def onClickedBtnAutoDrv(self):
        change_background_color(self.btnAutoDrv, self.checkBackgroundColor)
        change_text_color(self.btnAutoDrv, self.checkColor)
        change_background_color(self.btnRemoteDrv, self.defaultBackgroundColor)
        change_text_color(self.btnRemoteDrv, self.defaultColor)
        print("onClickedBtnAutoDrv")
    
    @Slot()
    def onClickedBtnRemoteDrv(self):
        change_background_color(self.btnAutoDrv, self.defaultBackgroundColor)
        change_text_color(self.btnAutoDrv, self.defaultColor)
        change_background_color(self.btnRemoteDrv, self.checkBackgroundColor)
        change_text_color(self.btnRemoteDrv, self.checkColor)
        print("onClickedBtnRemoteDrv")
    
    @Slot()
    def onClickedBtnOpticalMode(self):
        change_background_color(self.btnOpticalMode, self.checkBackgroundColor)
        change_text_color(self.btnOpticalMode, self.checkColor)
        change_background_color(self.btnIRMode, self.defaultBackgroundColor)
        change_text_color(self.btnIRMode, self.defaultColor)
        print("onClickedBtnOpticalMode")
    
    @Slot()
    def onClickedBtnIRMode(self):
        change_background_color(self.btnOpticalMode, self.defaultBackgroundColor)
        change_text_color(self.btnOpticalMode, self.defaultColor)
        change_background_color(self.btnIRMode, self.checkBackgroundColor)
        change_text_color(self.btnIRMode, self.checkColor)
        print("onClickedBtnIRMode")
    
    @Slot()
    def onClickedBtnScaleUp(self):
        change_background_color(self.btnScaleUp, self.checkBackgroundColor)
        change_text_color(self.btnScaleUp, self.checkColor)
        change_background_color(self.btnScaleDown, self.defaultBackgroundColor)
        change_text_color(self.btnScaleDown, self.defaultColor)
        print("onClickedBtnScaleUp")
    
    @Slot()
    def onClickedBtnScaleDown(self):
        change_background_color(self.btnScaleUp, self.defaultBackgroundColor)
        change_text_color(self.btnScaleUp, self.defaultColor)
        change_background_color(self.btnScaleDown, self.checkBackgroundColor)
        change_text_color(self.btnScaleDown, self.checkColor)
        print("onClickedBtnScaleDown")
    
    @Slot()
    def onClickedBtnUnLock(self):
        change_background_color(self.labelUnLock, self.checkBackgroundColor)
        change_text_color(self.labelUnLock, self.checkColor)
        change_background_color(self.labelLock, self.defaultBackgroundColor)
        change_text_color(self.labelLock, self.defaultColor)
        print("onClickedBtnUnLock")
    
    @Slot()
    def onClickedBtnLock(self):
        change_background_color(self.labelLock, self.checkBackgroundColor)
        change_text_color(self.labelLock, self.checkColor)
        change_background_color(self.labelUnLock, self.defaultBackgroundColor)
        change_text_color(self.labelUnLock, self.defaultColor)
        print("onClickedBtnLock")
    
    # 줌 버튼
    @Slot()
    def onClickedBtnZoomInMainScreen(self):
        print("onClickedBtnZoomInMainScreen")
        self.videoController.show_video_dialog()
    
    @Slot()
    def onClickedBtnZoomInBottomScreen(self):
        print("onClickedBtnZoomInBottomScreen")
    
    @Slot()
    def onClickedBtnZoomInBottomRightScreen(self):
        print("onClickedBtnZoomInBottomRightScreen")
    
    # ==================== 종료 처리 ====================
    
    def closeEvent(self, event):
        """윈도우 종료 이벤트"""
        print("closeEvent")

        self.netMMS.stop()
        self.netMMS.shutdown()
        

        self.videoController.cleanup()
        self.mapController.cleanup()
        self.statusManager.cleanup()
        self.closedSignal.emit()
        super().closeEvent(event)


if __name__ == '__main__':
    theApp = QApplication(sys.argv)
    form = MainForm()
    form.show()
    sys.exit(theApp.exec())
