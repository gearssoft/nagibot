import sys
from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtCore import Signal, QTimer, Qt, QThread
from PySide6.QtGui import QImage, QPixmap
import cv2
import numpy as np

import UI.mainForm

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

class MainForm(QWidget, UI.mainForm.Ui_mainForm):
    
    gotoHomeSignal = Signal()
    gotoSetupSignal = Signal()
    closedSignal = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        
        self.btnGoHome.clicked.connect(self.gotoHome)
        self.btnGotoSetup.clicked.connect(self.gotoSetup)
        
        # 초기 "준비 중" 메시지 표시
        self.mainCamScreen_bmpLabel.setText("영상 준비 중...")
        
        # RTSP 스트림 설정
        self.rtsp_url = "rtsp://gbox3d:71021707@gears001.iptime.org:21028/stream_ch00_0"
        
        # 비디오 스레드 생성 및 시작
        self.thread = VideoThread(self.rtsp_url)
        self.thread.change_pixmap_signal.connect(self.update_image)
        self.thread.start()
        
    def update_image(self, cv_img):
        """비디오 프레임을 업데이트하는 메서드"""
        rgb_image = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        convert_to_Qt_format = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
        p = convert_to_Qt_format.scaled(self.mainCamScreen.size(), Qt.KeepAspectRatio)
        self.mainCamScreen_bmpLabel.setPixmap(QPixmap.fromImage(p))
        
    def gotoHome(self):
        print("gotoHome")
        self.gotoHomeSignal.emit()
        
    def gotoSetup(self):
        print("gotoSetup")
        self.gotoSetupSignal.emit()
        
    def closeEvent(self, event):
        print("closeEvent")
        self.thread.stop()
        self.closedSignal.emit()
        super().closeEvent(event)

if __name__ == '__main__':
    theApp = QApplication(sys.argv)
    form = MainForm()
    form.show()
    sys.exit(theApp.exec())