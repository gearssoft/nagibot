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


# 정찰로봇 클라이언트 모듈 임포트
from robot_client import RobotClient

from random import randint
import sys
import os

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
        
class StatusUpdateThread(QThread):
    statusUpdateSignal = Signal()
    
    def __init__(self):
        super().__init__()
        self._run_flag = True

    def run(self):
        while self._run_flag:
            self.statusUpdateSignal.emit()
            self.sleep(10)  # 10초마다 상태 업데이트
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
        
        
        
        # Main Camera 비디오 스레드 생성 및 시작
        self.mainCameraThread = VideoThread(self.rtsp_url)
        self.mainCameraThread.change_pixmap_signal.connect(self.update_image)
        self.mainCameraThread.start()
        
        # 상태 업데이트 스레드 생성 및 시작
        # self.statusUpdateThread = StatusUpdateThread()
        # self.statusUpdateThread.statusUpdateSignal.connect(self.updateStatus)
        # self.statusUpdateThread.start()
        
        # VideoDialog 미리 생성
        self.video_dialog = VideoDialog()
        
        
        # subCamera Screen 
        self.labelSubCamera.setText(" 영싱준비중 ")
        #부모위젯의 크게에 맞춤
        match_widget_to_parent(self.labelSubCamera)
        self.labelSubCamera.setAlignment(Qt.AlignCenter)
        
        # self.subCameraThread = VideoThread(self.rtsp_url_subScreen)
        # self.subCameraThread.change_pixmap_signal.connect(self.update_image_SubCamera)
        # self.subCameraThread.start()


        self.detection_overlay_enabled = self.configMng.get_detection_server_enable()

    def update_image(self, cv_img):
        """비디오 프레임을 업데이트하는 메서드 - YOLO 감지 추가"""
        # # YOLO 감지 요청 (논블로킹)
        if hasattr(self, 'yolo_detection_thread'):
            self.yolo_detection_thread.detect_objects(cv_img)
        
        # # 현재 감지 결과가 있으면 이미지에 그리기
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