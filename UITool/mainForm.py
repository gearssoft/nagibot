"""
filename : MainForm.py
author : gbox3d

위 주석을 수정하지 마시오
"""
from random import randint
import sys
from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtCore import Signal, QTimer, Qt, QThread,Slot, QDateTime
from PySide6.QtGui import QImage, QPixmap, QTextCursor, QFont, QFontDatabase

from PySide6.QtWebEngineWidgets import QWebEngineView

import cv2
import numpy as np

import UI.mainForm

from cssutils import change_background_color, change_text_color
from videoFrame import VideoDialog
from my_qt_utils import match_widget_to_parent,limit_plaintext_lines

from configMng import ConfigManager

from detector_client import DetectionThread,draw_detections

from random import randint
import sys
import os


# 정찰로봇 클라이언트 모듈 임포트
from robot_client import RobotClient

class VideoThread(QThread):
    change_pixmap_signal = Signal(np.ndarray)

    def __init__(self, rtsp_url):
        super().__init__()
        self.rtsp_url = rtsp_url
        self._run_flag = True
        self._cap = None

    def run(self):
        # cap = cv2.VideoCapture(self.rtsp_url)
        # while self._run_flag:
        #     ret, cv_img = cap.read()
        #     if ret:
        #         self.change_pixmap_signal.emit(cv_img)
        # cap.release()

        # RTSP가 종료 시 블로킹되지 않도록 타임아웃/버퍼 최소화
        os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS",
                                "rtsp_transport;tcp|stimeout;2000000")  # 2초
        self._cap = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)
        try:
            self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception:
            pass
            print("VideoThread: CAP_PROP_BUFFERSIZE 설정 실패, FFMPEG 버전이 낮을 수 있습니다.")
        
        print("VideoThread: RTSP URL:", self.rtsp_url)
        
        while self._run_flag:
            if not self._cap.isOpened():
                self.msleep(50)
                continue
            ret, cv_img = self._cap.read()
            if not ret:
                self.msleep(10)
                continue
            self.change_pixmap_signal.emit(cv_img)
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def stop(self):
        self._run_flag = False
        self.wait()
        
# class StatusUpdateThread(QThread):
#     statusUpdateSignal = Signal()
    
#     def __init__(self):
#         super().__init__()
#         self._run_flag = True

#     def run(self):
#         while self._run_flag:
#             self.statusUpdateSignal.emit()
#             self.sleep(10)  # 10초마다 상태 업데이트
#             pass

#     def stop(self):
#         self._run_flag = False
#         self.wait()

class MainForm(QWidget, UI.mainForm.Ui_mainForm):
    
    gotoHomeSignal = Signal()
    gotoSetupSignal = Signal()
    closedSignal = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)

        # load font
        # QFontDatabase.addApplicationFont(":/font/font/DungGeunMo.ttf")
        
        self.configMng = ConfigManager()
        if self.configMng.load_config() == True:
            print("ConfigManager: 설정 파일 로드 성공")
            
            print("ConfigManager: 차량 IP 목록:", [car['ip'] for car in self.configMng.config['cars']])
            print("ConfigManager: 차량 포트 목록:", [car['port'] for car in self.configMng.config['cars']])
            print("ConfigManager: 차량 카메라 URL 목록:", [car['camUrl'] for car in self.configMng.config['cars']])
            print("ConfigManager: 이미지 감지 서버 IP:", self.configMng.config['imageDetectionServer']['ip'])
            print("ConfigManager: 이미지 감지 서버 포트:", self.configMng.config['imageDetectionServer']['port'])
            
        else:
            print("ConfigManager: 설정 파일 로드 실패")
            # 에러 종료
            sys.exit(-1)
        
        # 폰트 파일 추가
        font_id = QFontDatabase.addApplicationFont(":/font/font/D2Coding-Ver1.3.2-20180524.ttf")
        if font_id != -1:  # 폰트 로드 성공 시
            font_families = QFontDatabase.applicationFontFamilies(font_id)
            if font_families:
                font_family = font_families[0]  # 첫 번째 폰트 패밀리를 선택
                self.font_d2coding = font_family
                print("D2Coding 폰트 로드 성공")
        else:
            self.font_d2coding = None
            print("D2Coding 폰트 로드 실패")
            # 에러 종료
            sys.exit(-1)
            
        self.setupUi(self)
        
        
        
        # 모든 UI 요소에 D2Coding 폰트 패밀리 적용
        widgets = self.findChildren(QWidget)  # 모든 자식 위젯 찾기
        for widget in widgets:
            font = widget.font()  # 기존 폰트 가져오기
            font.setFamily(self.font_d2coding)  # 폰트 패밀리 변경
            widget.setFont(font)  # 변경된 폰트를 위젯에 설정
        
        
        self.btnGoHome.clicked.connect(self.gotoHome)
        self.btnGotoSetup.clicked.connect(self.gotoSetup)
        
        # 키 버튼 눌림/떨어짐 표시용 레이블 숨김
        self.label_keyup_normal.setVisible(True)
        self.label_keyup_push.setVisible(False)
        
        self.label_keydown_normal.setVisible(True)
        self.label_keydown_push.setVisible(False)
        
        self.label_keyleft_normal.setVisible(True)
        self.label_keyleft_push.setVisible(False)
        
        self.label_keyright_normal.setVisible(True)
        self.label_keyright_push.setVisible(False)
        
        
        # Connect the button pressed and released signals to show and hide the labels
        self.btnKeyUp.pressed.connect(self.keyUpPressed)
        self.btnKeyUp.released.connect(self.keyUpReleased)
        
        self.btnKeyDown.pressed.connect(self.keyDownPressed)
        self.btnKeyDown.released.connect(self.keyDownReleased)
        
        self.btnKeyLeft.pressed.connect(self.keyLeftPressed)
        self.btnKeyLeft.released.connect(self.keyLeftReleased)
        
        self.btnKeyRight.pressed.connect(self.keyRightPressed)
        self.btnKeyRight.released.connect(self.keyRightReleased)
        
        #비상정지버튼
        self.btnAbnormalStop.pressed.connect(self.btnAbnormalStopPressed)
        self.btnAbnormalStop.released.connect(self.btnAbnormalStopReleased)
        self.btnAbnormalStop.clicked.connect(self.btnAbnormalStopClicked)
        
        
        # mode select button
        # 배경색 설정
        self.checkColor = "#000000"
        self.checkBackgroundColor = "rgb(188, 215, 236)"
        self.defaultBackgroundColor = "#ffffff"
        self.defaultColor = "#000000"
        
        change_background_color(self.btnAutoDrv, self.checkBackgroundColor)
        change_text_color(self.btnAutoDrv, self.checkColor)
        
        change_background_color(self.btnRemoteDrv, self.defaultBackgroundColor)
        change_text_color(self.btnRemoteDrv, self.defaultColor)
        
        self.btnAutoDrv.clicked.connect(self.onClickedBtnAutoDrv)
        self.btnRemoteDrv.clicked.connect(self.onClickedBtnRemoteDrv)
        
        change_background_color(self.btnOpticalMode, self.checkBackgroundColor)
        change_text_color(self.btnOpticalMode, self.checkColor)
        
        change_background_color(self.btnIRMode, self.defaultBackgroundColor)
        change_text_color(self.btnIRMode, self.defaultColor)
        
        self.btnOpticalMode.clicked.connect(self.onClickedBtnOpticalMode)
        self.btnIRMode.clicked.connect(self.onClickedBtnIRMode)
        
        change_background_color(self.btnScaleUp, self.checkBackgroundColor)
        change_text_color(self.btnScaleUp, self.checkColor)
        
        change_background_color(self.btnScaleDown, self.defaultBackgroundColor)
        change_text_color(self.btnScaleDown, self.defaultColor)
        
        self.btnScaleUp.clicked.connect(self.onClickedBtnScaleUp)
        self.btnScaleDown.clicked.connect(self.onClickedBtnScaleDown)
        
        
        change_background_color(self.labelUnLock, self.checkBackgroundColor)
        change_text_color(self.labelUnLock, self.checkColor)
        
        change_background_color(self.labelLock, self.defaultBackgroundColor)
        change_text_color(self.labelLock, self.defaultColor)
        
        self.btnUnLock.clicked.connect(self.onClickedBtnUnLock)
        self.btnLock.clicked.connect(self.onClickedBtnLock)
        
        # zoom in/out button
        self.btnZoomInMainScreen.clicked.connect(self.onClickedBtnZoomInMainScreen)
        self.btnZoomInBottomScreen.clicked.connect(self.onClickedBtnZoomInBottomScreen)
        self.btnZoomInBottomRightScreen.clicked.connect(self.onClickedBtnZoomInBottomRightScreen)
        
        self.systemBeginTime = QDateTime.currentDateTime()

        # 호기 표시
        self.txUnitNuberInfo.setText("1 호기"); # 호기 표시를 비워둠
        
        # 초기 "준비 중" 메시지 표시
        self.mainCamScreen_bmpLabel.setText("영상 준비 중...")
        # 화면 중앙에 텍스트 정렬 ,크기는 24, 굵기는 75
        self.mainCamScreen_bmpLabel.setAlignment(Qt.AlignCenter)
        self.mainCamScreen_bmpLabel.setFont(QFont(self.font_d2coding, 24, 75))
        
        # RTSP 스트림 설정
        self.rtsp_url = self.configMng.get_car_cam_url(car_idx=0)
        self.rtsp_url_subScreen = self.configMng.get_car_cam_url(car_idx=1)
        
        print("RTSP URL:", self.rtsp_url)
        print("RTSP URL SubScreen:", self.rtsp_url_subScreen)
        
        # ──────────── 이미지 감지 서버로 프레임 전송 세팅 ────────────
        self.detection_overlay_enabled = False  # 감지 결과 표시 여부
        if self.configMng.get_detection_server_enable() is True:
            det_ip = self.configMng.get_detection_server_ip()
            det_port = self.configMng.get_detection_server_port()
            
            # YOLO 감지 쓰레드 생성
            self.yolo_detection_thread = DetectionThread(host=det_ip, port=det_port)
            self.yolo_detection_thread.detection_results.connect(self.onYOLODetectionResults)
            self.yolo_detection_thread.status_update.connect(self.onYOLOStatus)
            self.yolo_detection_thread.start_detection()
            
            # 감지 결과를 저장할 변수
            self.current_detections = []
            self.detection_overlay_enabled = True  # 감지 결과 표시 여부

        # ────────────────────────────────────────────────────────

        # 상태 업데이트 타이머 설정
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self.updateStatus)
        self.status_timer.start(10000)  # 10초마다

        # ────────────────────────────────────────────────────────
        
        
        # Main Camera 비디오 스레드 생성 및 시작
        self.mainCameraThread = VideoThread(self.rtsp_url)
        self.mainCameraThread.change_pixmap_signal.connect(self.update_image)
        self.mainCameraThread.start()
        
        # VideoDialog 미리 생성
        self.video_dialog = VideoDialog()


        # subCamera Screen
        self.labelSubCamera.setText(" 영상 준비 중 ")
        #부모위젯의 크게에 맞춤
        match_widget_to_parent(self.labelSubCamera)
        self.labelSubCamera.setAlignment(Qt.AlignCenter)
        
        self.subCameraThread = VideoThread(self.rtsp_url_subScreen)
        self.subCameraThread.change_pixmap_signal.connect(self.update_image_SubCamera)
        self.subCameraThread.start()
        
        #지도화면
        # 대한민국 부안 앞바다 근처의 위도, 경도 및 줌 레벨 설정
        latitude = 35.7299    # 위도 (부안 앞바다 근처)
        longitude = 126.5833  # 경도 (부안 앞바다 근처)
        zoom = 13             # 줌 레벨 (적절한 확대 비율)

        # OpenStreetMap URL 설정
        map_url = f"https://www.openstreetmap.org/#map={zoom}/{latitude}/{longitude}"
        # OpenStreetMap URL 설정
        # map_url = f"https://www.openstreetmap.org/#map={zoom}/{latitude}/{longitude}"
        self.labelBottomRightScreen.setText("지도 준비 중")
        match_widget_to_parent(self.labelBottomRightScreen)
        
        self.labelBottomRightScreen.setAlignment(Qt.AlignCenter)
        self.web_view = QWebEngineView(self.widgetBottomRightScreen)
        self.web_view.setUrl(map_url)
        #맨뒤로 보내기
        self.web_view.lower()
        self.labelBottomRightScreen.lower()
        match_widget_to_parent(self.web_view)
        
        
        # 로봇 클라이언트 초기화 및 연결
        # configMng에서 첫 번째 차량(0번 인덱스)의 IP와 포트를 가져와 사용

        self.edLogText.appendPlainText("로봇 클라이언트 초기화 및 연결 시작")

        cars_units = [
            { "ip": self.configMng.get_car_ip(0), "port": self.configMng.get_car_port(0), "camUrl": self.configMng.get_car_cam_url(0), "enable": self.configMng.get_unit_enable(0) },
            { "ip": self.configMng.get_car_ip(1), "port": self.configMng.get_car_port(1), "camUrl": self.configMng.get_car_cam_url(1), "enable": self.configMng.get_unit_enable(1) },
            { "ip": self.configMng.get_car_ip(2), "port": self.configMng.get_car_port(2), "camUrl": self.configMng.get_car_cam_url(2), "enable": self.configMng.get_unit_enable(2) }
        ]

        self.robotClients = []
        self.activeRobot=None

        for idx, car in enumerate(cars_units):
            print(f"Unit {idx+1} - IP: {car['ip']}, Port: {car['port']}, Cam URL: {car['camUrl']}, Enable: {car['enable']}")
            if car['enable']:
                robot_ip = car['ip']
                robot_port = car['port']

                if robot_port is not 0 and robot_ip is not None:
                    print(f"로봇 클라이언트 연결시도 (IP: {robot_ip}, 포트: {robot_port})")
                    _client = RobotClient(host=robot_ip, port=robot_port)
                    if _client.connect():
                        print(f"로봇 클라이언트 연결 성공 (IP: {robot_ip}, 포트: {robot_port})")
                        # _client.on_sensor_updated = self.handleSensorUpdate
                        _client.on_sensor_updated = (lambda rc=_client: self.handleSensorUpdate(rc))
                        _client.on_drive_ack = (lambda rc=_client: self.onDriveAck(rc))

                        self.robotClients.append(_client)

                        if self.activeRobot is None:
                            self.activeRobot = _client
                    else:
                        print(f"로봇 클라이언트 연결 실패 (IP: {robot_ip}, 포트: {robot_port})")
                        self.edLogText.appendPlainText(f"로봇 클라이언트 연결 실패 (IP: {robot_ip}, 포트: {robot_port})")
                else:
                    print(f"로봇 {idx+1} 비활성 상태 port 0 또는 IP 없음")
                    self.edLogText.appendPlainText(f"로봇 {idx+1} 비활성 상태 port 0 또는 IP 없음")
                break;

        self.edLogText.appendPlainText("로봇 클라이언트 초기화 및 연결 완료")
        
    @Slot(object)
    def onDriveAck(self, robotClient):
        # print("onDriveAck from", robotClient.id)
        _drive_status = robotClient.get_drive_status()
        print("Drive Status:", _drive_status)
        self.edLogText.appendPlainText(f"Drive Ack - Speed: {_drive_status['speed']:.2f} m/s, Yaw: {_drive_status['yaw']:.2f} rad/s, Position: {_drive_status['position']}")

    @Slot(object)
    def handleSensorUpdate(self,robotClient):
        print("handleSensorUpdate")
        # robotClient 쓰레드에서 호출되므로, 메인 쓰레드로 UI 업데이트를 전달합니다.
        # QTimer.singleShot(0, self.updateSensorUI)
        # sensor_data = self.robotClient.get_sensor_data()
        sensor_data = robotClient.get_sensor_data()
        
        sensor1 = sensor_data['sensors'][1]
        print("Sensor 1:", sensor1)
        print("Sensor 1 Temperature:", sensor1.temperature)
        
            
    @Slot()
    def updateStatus(self):
        #print("updateStatus")
        wifiStatus = randint(1, 4)
        # print("wifiStatus:", wifiStatus)
        self.wifiStatus.setPixmap(QPixmap(f":/와이파이{wifiStatus}.png"))
        
        networkStatus = randint(1, 5)
        self.networkStatus.setPixmap(QPixmap(f":/네트워크{networkStatus}.png"))
        
        batteryStatus = randint(1, 5)
        self.batteryStatus.setPixmap(QPixmap(f":/배터리{batteryStatus}.png"))
        
        
        # yyyy-mm-dd hh:mm:ss
        # 현재 시간을 표시
        _currentTime = QDateTime.currentDateTime()
        self.currentTime.setText(_currentTime.toString("yyyy-MM-dd hh:mm:ss"))
        
        
        # 시스템 시작 후 경과 시간을 표시
        _elapsedTime = self.systemBeginTime.secsTo(_currentTime)
        self.operationTime.setText(f"{_elapsedTime // 3600:02d}:{(_elapsedTime % 3600) // 60:02d}:{_elapsedTime % 60:02d}")
        
        #날씨 정보 표시
        self.labelAreaName.setText( "전주시 경원동")
        self.labelWether.setText("맑음 또는 흐림 그리고 비 또는 눈")
        
        temperature = randint(-10, 40)
        rainSize = randint(0, 100)
        windy = randint(0, 100)
        humidity = randint(0, 100)
        precipitation = randint(0, 100)
        waveHeight = randint(0, 100)
        
        self.labelTemper.setText(f"기온: {temperature}℃")
        self.labelRain.setText(f"강수량: {rainSize}mm")
        self.labelWindy.setText(f"풍속: {windy}m/s")
        self.labelHumidty.setText(f"습도: {humidity}%")
        self.labelPrecipitation.setText(f"강수확률: {precipitation}%")
        self.labelWaveHeight.setText(f"파고: {waveHeight}m")
       
        # log 정보 표시
        self.edLogText.appendPlainText(f"{_currentTime.toString('yyyy-MM-dd hh:mm:ss')} - 기온: {temperature}℃, 강수량: {rainSize}mm, 풍속: {windy}m/s, 습도: {humidity}%, 강수확률: {precipitation}%, 파고: {waveHeight}m")
        limit_plaintext_lines(self.edLogText, 10)
        
        # if self.edLogText.blockCount() > 10:
        #     cursor = self.edLogText.textCursor()
            
        #     # 커서를 맨 위로 이동
        #     cursor.movePosition(QTextCursor.Start)
            
        #     # 첫 번째 줄 선택
        #     cursor.movePosition(QTextCursor.StartOfBlock)
        #     cursor.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
            
        #     # 선택된 텍스트를 제거
        #     cursor.removeSelectedText()
        #     cursor.deleteChar()  # 줄 바꿈 문자 제거
            
        #     # 변경된 커서를 다시 설정
        #     self.edLogText.setTextCursor(cursor)
    
    # main camera 화면에 비디오 프레임을 업데이트하는 메서드
    #############################################################################
    @Slot(np.ndarray)
    def update_image(self, cv_img):
        """비디오 프레임을 업데이트하는 메서드 - YOLO 감지 추가"""
        # YOLO 감지 요청 (논블로킹)
        if hasattr(self, 'yolo_detection_thread'):
            self.yolo_detection_thread.detect_objects(cv_img)
        
        # 현재 감지 결과가 있으면 이미지에 그리기
        display_image = cv_img.copy()
        if self.detection_overlay_enabled and self.current_detections:
            display_image = draw_detections(display_image, self.current_detections)
        
        # Qt 형식으로 변환하여 화면에 표시
        rgb_image = cv2.cvtColor(display_image, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        convert_to_Qt_format = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
        p = convert_to_Qt_format.scaled(self.mainCamScreen.size(), Qt.KeepAspectRatio)
        self.mainCamScreen_bmpLabel.setPixmap(QPixmap.fromImage(p))
        
        # VideoDialog에도 감지 결과가 포함된 이미지 전달
        if self.video_dialog.isVisible():
            self.video_dialog.update_video_frame(QPixmap.fromImage(p))
    
    @Slot(list, np.ndarray)
    def onYOLODetectionResults(self, detections, original_image):
        """YOLO 감지 결과 처리"""
        self.current_detections = detections
        
        # 감지 결과 로그
        if detections:
            detection_summary = ", ".join([f"{d['name']}({d['confidence']:.2f})" for d in detections[:3]])
            if len(detections) > 3:
                detection_summary += f" 외 {len(detections)-3}개"
            log_msg = f"[detetor] 감지: {detection_summary}"
        else:
            log_msg = "[detector] 객체 감지되지 않음"
            
        self.edLogText.appendPlainText(log_msg)
        limit_plaintext_lines(self.edLogText, 10)
    
    @Slot(str)
    def onYOLOStatus(self, msg):
        """YOLO 상태 메시지 처리"""
        self.edLogText.appendPlainText(f"[Detector] {msg}")
        limit_plaintext_lines(self.edLogText, 10)
    
    def toggle_detection_overlay(self, enabled: bool):
        """감지 결과 오버레이 표시 토글"""
        self.detection_overlay_enabled = enabled
        
    def clear_detections(self):
        """현재 감지 결과 초기화"""
        self.current_detections = []
        
    #############################################################################
            
    @Slot(np.ndarray)
    def update_image_SubCamera(self, cv_img):
        """비디오 프레임을 업데이트하는 메서드"""
        rgb_image = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        convert_to_Qt_format = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
        p = convert_to_Qt_format.scaled(self.labelSubCamera.size(), Qt.KeepAspectRatio)
        self.labelSubCamera.setPixmap(QPixmap.fromImage(p))
        
        # if self.video_dialog.isVisible():
        #     self.video_dialog.update_video_frame(QPixmap.fromImage(p))
            
        
    @Slot()
    def onClickedBtnZoomInMainScreen(self):
        print("onClickedBtnZoomInMainScreen")
        # VideoDialog 창 열기
        if not self.video_dialog.isVisible():
            self.video_dialog.show()
        
    @Slot()
    def onClickedBtnZoomInBottomScreen(self):
        print("onClickedBtnZoomInBottomScreen")
    @Slot()
    def onClickedBtnZoomInBottomRightScreen(self):
        print("onClickedBtnZoomInBottomRightScreen")
        
    @Slot()
    def gotoHome(self):
        print("gotoHome")
        self.gotoHomeSignal.emit()
    
    @Slot()
    def gotoSetup(self):
        print("gotoSetup")
        self.gotoSetupSignal.emit()
        
    @Slot()
    def keyUpPressed(self):
        self.label_keyup_normal.setVisible(False)
        self.label_keyup_push.setVisible(True)
        # 전진 명령
        self.activeRobot.send_drive_command(1.0, 0.0)

    @Slot()
    def keyUpReleased(self):
        self.label_keyup_normal.setVisible(True)
        self.label_keyup_push.setVisible(False)
        # 정지 명령
        self.activeRobot.send_drive_command(0.0, 0.0)
        
    @Slot()
    def keyDownPressed(self):
        self.label_keydown_normal.setVisible(False)
        self.label_keydown_push.setVisible(True)
        # 후진 명령
        self.activeRobot.send_drive_command(-1.0, 0.0)
    
    @Slot()
    def keyDownReleased(self):
        self.label_keydown_normal.setVisible(True)
        self.label_keydown_push.setVisible(False)
        # 정지 명령
        self.activeRobot.send_drive_command(0.0, 0.0)
        
    @Slot()
    def keyLeftPressed(self):
        self.label_keyleft_normal.setVisible(False)
        self.label_keyleft_push.setVisible(True)
        # 좌회전 명령
        self.activeRobot.send_drive_command(0.5, 0.5)
        
    
    @Slot()
    def keyLeftReleased(self):
        self.label_keyleft_normal.setVisible(True)
        self.label_keyleft_push.setVisible(False)
        # 정지 명령
        self.activeRobot.send_drive_command(0.0, 0.0)
        
    @Slot()
    def keyRightPressed(self):
        self.label_keyright_normal.setVisible(False)
        self.label_keyright_push.setVisible(True)
        # 우회전 명령
        self.activeRobot.send_drive_command(0.5, -0.5)
        
    @Slot()
    def keyRightReleased(self):
        self.label_keyright_normal.setVisible(True)
        self.label_keyright_push.setVisible(False)
        # 정지 명령
        self.activeRobot.send_drive_command(0.0, 0.0)
        
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
        
        print("onClickedBtnManualDrv")
        
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
    
    def closeEvent(self, event):
        print("closeEvent")
        self.mainCameraThread.stop()
        # self.statusUpdateThread.stop()  
        self.closedSignal.emit()
        super().closeEvent(event)

if __name__ == '__main__':
    theApp = QApplication(sys.argv)
    form = MainForm()
    form.show()
    sys.exit(theApp.exec())