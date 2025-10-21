"""
filename: MainForm.py
author: gbox3d

위 주석을 수정하지 마시오
"""
import sys
from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtCore import Signal, Slot
from PySide6.QtGui import QFontDatabase

import UI.mainForm
from cssutils import change_background_color, change_text_color
from my_qt_utils import match_widget_to_parent
from configMng import ConfigManager
from robot_client import RobotClient

# 리팩토링된 컨트롤러 및 매니저 임포트
from video_controller import VideoController
from map_controller import MapController
from status_manager import StatusManager


class MainForm(QWidget, UI.mainForm.Ui_mainForm):
    
    gotoHomeSignal = Signal()
    gotoSetupSignal = Signal()
    closedSignal = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 설정 관리자 초기화
        self._initialize_config()
        
        # 폰트 초기화
        self._initialize_font()
        
        # UI 설정
        self.setupUi(self)
        self._apply_font_to_all_widgets()
        
        # 버튼 시그널 연결
        self._connect_signals()
        
        # UI 초기화
        self._initialize_ui_state()
        
        # 컨트롤러 및 매니저 초기화
        self._initialize_controllers()
        
        # 로봇 클라이언트 초기화
        self._initialize_robot_clients()
        
        # 타이머 시작
        self.statusManager.initialize_timers(
            self._update_clock,
            self._update_status
        )
    
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
    
    def _initialize_font(self):
        """폰트 로드 및 초기화"""
        font_id = QFontDatabase.addApplicationFont(":/font/font/D2Coding-Ver1.3.2-20180524.ttf")
        if font_id != -1:
            font_families = QFontDatabase.applicationFontFamilies(font_id)
            if font_families:
                self.font_d2coding = font_families[0]
                print("D2Coding 폰트 로드 성공")
                return
        
        print("D2Coding 폰트 로드 실패")
        sys.exit(-1)
    
    def _apply_font_to_all_widgets(self):
        """모든 UI 요소에 D2Coding 폰트 적용"""
        widgets = self.findChildren(QWidget)
        for widget in widgets:
            font = widget.font()
            font.setFamily(self.font_d2coding)
            widget.setFont(font)
    
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
        
        # 비상정지 버튼
        self.btnAbnormalStop.pressed.connect(self.btnAbnormalStopPressed)
        self.btnAbnormalStop.released.connect(self.btnAbnormalStopReleased)
        self.btnAbnormalStop.clicked.connect(self.btnAbnormalStopClicked)
        
        # 모드 선택 버튼
        self.btnAutoDrv.clicked.connect(self.onClickedBtnAutoDrv)
        self.btnRemoteDrv.clicked.connect(self.onClickedBtnRemoteDrv)
        self.btnOpticalMode.clicked.connect(self.onClickedBtnOpticalMode)
        self.btnIRMode.clicked.connect(self.onClickedBtnIRMode)
        self.btnScaleUp.clicked.connect(self.onClickedBtnScaleUp)
        self.btnScaleDown.clicked.connect(self.onClickedBtnScaleDown)
        self.btnUnLock.clicked.connect(self.onClickedBtnUnLock)
        self.btnLock.clicked.connect(self.onClickedBtnLock)
        
        # 줌 버튼
        self.btnZoomInMainScreen.clicked.connect(self.onClickedBtnZoomInMainScreen)
        self.btnZoomInBottomScreen.clicked.connect(self.onClickedBtnZoomInBottomScreen)
        self.btnZoomInBottomRightScreen.clicked.connect(self.onClickedBtnZoomInBottomRightScreen)
    
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
    
    def _initialize_robot_clients(self):
        """로봇 클라이언트 초기화 및 연결"""
        self.edLogText.appendPlainText("로봇 클라이언트 초기화 및 연결 시작")
        
        cars_units = [
            {
                "ip": self.configMng.get_car_ip(i),
                "port": self.configMng.get_car_port(i),
                "camUrl": self.configMng.get_car_cam_url(i),
                "enable": self.configMng.get_unit_enable(i)
            }
            for i in range(3)
        ]
        
        self.robotClients = []
        self.activeRobot = None
        
        for idx, car in enumerate(cars_units):
            if not car['enable']:
                print(f"로봇 {idx+1} 비활성 상태")
                continue
            
            robot_ip = car['ip']
            robot_port = car['port']
            
            if robot_port == 0 or robot_ip is None:
                print(f"로봇 {idx+1} 비활성 상태 port 0 또는 IP 없음")
                self.edLogText.appendPlainText(f"로봇 {idx+1} 비활성 상태 port 0 또는 IP 없음")
                continue
            
            print(f"로봇 클라이언트 연결시도 (IP: {robot_ip}, 포트: {robot_port})")
            client = RobotClient(host=robot_ip, port=robot_port)
            
            if client.connect():
                print(f"로봇 클라이언트 연결 성공 (IP: {robot_ip}, 포트: {robot_port})")
                client.on_sensor_updated = (lambda rc=client: self.handleSensorUpdate(rc))
                client.on_drive_ack = (lambda rc=client: self.onDriveAck(rc))
                
                self.robotClients.append(client)
                
                if self.activeRobot is None:
                    self.activeRobot = client
            else:
                print(f"로봇 클라이언트 연결 실패 (IP: {robot_ip}, 포트: {robot_port})")
                self.edLogText.appendPlainText(f"로봇 클라이언트 연결 실패 (IP: {robot_ip}, 포트: {robot_port})")
        
        self.edLogText.appendPlainText("로봇 클라이언트 초기화 및 연결 완료")
    
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
    
    # ==================== 로봇 관련 콜백 ====================
    
    @Slot(object)
    def onDriveAck(self, robotClient):
        """주행 명령 응답 처리"""
        drive_status = robotClient.get_drive_status()
        print("Drive Status:", drive_status)
        self.edLogText.appendPlainText(
            f"Drive Ack - Speed: {drive_status['speed']:.2f} m/s, "
            f"Yaw: {drive_status['yaw']:.2f} rad/s, "
            f"Position: {drive_status['position']}"
        )
    
    @Slot(object)
    def handleSensorUpdate(self, robotClient):
        """센서 데이터 업데이트 처리"""
        print("handleSensorUpdate")
        sensor_data = robotClient.get_sensor_data()
        sensor1 = sensor_data['sensors'][1]
        print("Sensor 1:", sensor1)
        print("Sensor 1 Temperature:", sensor1.temperature)
    
    # ==================== 버튼 이벤트 핸들러 ====================
    
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
