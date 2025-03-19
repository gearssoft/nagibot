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

# 정찰로봇 클라이언트 모듈 임포트
from robot_client import RobotClient

class VideoThread(QThread):
    change_pixmap_signal = Signal(np.ndarray)

    def __init__(self, rtsp_url):
        super().__init__()
        self.rtsp_url = rtsp_url
        self._run_flag = True

    def run(self):
        cap = cv2.VideoCapture(self.rtsp_url)
        while self._run_flag:
            ret, cv_img = cap.read()
            if ret:
                self.change_pixmap_signal.emit(cv_img)
        cap.release()

    def stop(self):
        self._run_flag = False
        self.wait()
        
class StatusUpdateThread(QThread):
    statusUpdateSignal = Signal()
    
    def __init__(self):
        super().__init__()
        self._run_flag = True

    def run(self):
        while self._run_flag:
            self.statusUpdateSignal.emit()
            self.sleep(1)
            pass

    def stop(self):
        self._run_flag = False
        self.wait()

class MainForm(QWidget, UI.mainForm.Ui_mainForm):
    
    gotoHomeSignal = Signal()
    gotoSetupSignal = Signal()
    closedSignal = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        # load font
        QFontDatabase.addApplicationFont(":/font/font/DungGeunMo.ttf")
        
        self.configMng = ConfigManager()
        self.configMng.load_config()
        
        
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
        
        
        # # wifi status label
        # self.wifiStatus.setPixmap(QPixmap(":/와이파이3.png"))
        
        self.systemBeginTime = QDateTime.currentDateTime()
        
        # 초기 "준비 중" 메시지 표시
        self.mainCamScreen_bmpLabel.setText("영상 준비 중...")
        # 화면 중앙에 텍스트 정렬 ,크기는 24, 굵기는 75
        self.mainCamScreen_bmpLabel.setAlignment(Qt.AlignCenter)
        self.mainCamScreen_bmpLabel.setFont(QFont(self.font_d2coding, 24, 75))
        
        # RTSP 스트림 설정
        # self.rtsp_url = "rtsp://gbox3d:71021707@gears001.iptime.org:21028/stream_ch00_0"
        self.rtsp_url = self.configMng.get_car_cam_url()
        #충청남도 천안시 서북구 신당동 482-22	
        self.rtsp_url_subScreen = self.configMng.get_car_cam_url(1)
        # self.rtsp_url = "rtsp://rtspstream.com/pattern"
        
        
        # Main Camera 비디오 스레드 생성 및 시작
        self.mainCameraThread = VideoThread(self.rtsp_url)
        self.mainCameraThread.change_pixmap_signal.connect(self.update_image)
        self.mainCameraThread.start()
        
        # 상태 업데이트 스레드 생성 및 시작
        self.statusUpdateThread = StatusUpdateThread()
        self.statusUpdateThread.statusUpdateSignal.connect(self.updateStatus)
        self.statusUpdateThread.start()
        
        # VideoDialog 미리 생성
        self.video_dialog = VideoDialog()
        
        
        # subCamera Screen 
        self.labelSubCamera.setText(" 영싱준비중 ")
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
        self.robotClient = RobotClient()
        if self.robotClient.connect() :
            print("로봇 클라이언트 연결 성공")
            self.robotClient.on_sensor_updated = self.handleSensorUpdate
        else:
            print("로봇 클라이언트 연결 실패")
            
    @Slot()
    def handleSensorUpdate(self):
        print("handleSensorUpdate")
        # robotClient 쓰레드에서 호출되므로, 메인 쓰레드로 UI 업데이트를 전달합니다.
        # QTimer.singleShot(0, self.updateSensorUI)
        sensor_data = self.robotClient.get_sensor_data()
        
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
    
    @Slot(np.ndarray)
    def update_image(self, cv_img):
        """비디오 프레임을 업데이트하는 메서드"""
        rgb_image = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        convert_to_Qt_format = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
        p = convert_to_Qt_format.scaled(self.mainCamScreen.size(), Qt.KeepAspectRatio)
        self.mainCamScreen_bmpLabel.setPixmap(QPixmap.fromImage(p))
        
        if self.video_dialog.isVisible():
            self.video_dialog.update_video_frame(QPixmap.fromImage(p))
            
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
        self.robotClient.send_drive_command(1.0, 0.0)
    
    @Slot()
    def keyUpReleased(self):
        self.label_keyup_normal.setVisible(True)
        self.label_keyup_push.setVisible(False)
        # 정지 명령
        self.robotClient.send_drive_command(0.0, 0.0)
        
    @Slot()
    def keyDownPressed(self):
        self.label_keydown_normal.setVisible(False)
        self.label_keydown_push.setVisible(True)
        # 후진 명령
        self.robotClient.send_drive_command(-1.0, 0.0)
    
    @Slot()
    def keyDownReleased(self):
        self.label_keydown_normal.setVisible(True)
        self.label_keydown_push.setVisible(False)
        # 정지 명령
        self.robotClient.send_drive_command(0.0, 0.0)
        
    @Slot()
    def keyLeftPressed(self):
        self.label_keyleft_normal.setVisible(False)
        self.label_keyleft_push.setVisible(True)
        # 좌회전 명령
        self.robotClient.send_drive_command(0.5, 0.5)
        
    
    @Slot()
    def keyLeftReleased(self):
        self.label_keyleft_normal.setVisible(True)
        self.label_keyleft_push.setVisible(False)
        # 정지 명령
        self.robotClient.send_drive_command(0.0, 0.0)
        
    @Slot()
    def keyRightPressed(self):
        self.label_keyright_normal.setVisible(False)
        self.label_keyright_push.setVisible(True)
        # 우회전 명령
        self.robotClient.send_drive_command(0.5, -0.5)
        
    @Slot()
    def keyRightReleased(self):
        self.label_keyright_normal.setVisible(True)
        self.label_keyright_push.setVisible(False)
        # 정지 명령
        self.robotClient.send_drive_command(0.0, 0.0)
        
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
        self.statusUpdateThread.stop()  # 추가
        self.closedSignal.emit()
        super().closeEvent(event)

if __name__ == '__main__':
    theApp = QApplication(sys.argv)
    form = MainForm()
    form.show()
    sys.exit(theApp.exec())