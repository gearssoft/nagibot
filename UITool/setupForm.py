import sys
from PySide6.QtWidgets import QApplication ,QWidget
from PySide6.QtCore import Signal

from configMng import ConfigManager

import UI.setupForm

class setupForm(QWidget,UI.setupForm.Ui_SetupForm):
    
    closedSignal = Signal()
    backSignal = Signal()
    
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setupUi(self)
        
        self.configMng = ConfigManager()
        self.configMng.load_config()
        
        self.textEditCar1ip.setText(self.configMng.get_car_ip(0))
        self.textEditCar1port.setText(str(self.configMng.get_car_port(0)))
        self.textEditCar1Camurl.setText(self.configMng.get_car_cam_url(0))
        self.textEditCar1Camurl_IR.setText(self.configMng.get_car_cam_url_ir(0))
        self.cbUnitEnable_1.setChecked(self.configMng.get_unit_enable(0))
        
        self.textEditCar2ip.setText(self.configMng.get_car_ip(1))
        self.textEditCar2port.setText(str(self.configMng.get_car_port(1)))
        self.textEditCar2Camurl.setText(self.configMng.get_car_cam_url(1))
        self.textEditCar2Camurl_IR.setText(self.configMng.get_car_cam_url_ir(1))
        self.cbUnitEnable_2.setChecked(self.configMng.get_unit_enable(1))

        self.textEditCar3ip.setText(self.configMng.get_car_ip(2))
        self.textEditCar3port.setText(str(self.configMng.get_car_port(2)))
        self.textEditCar3Camurl.setText(self.configMng.get_car_cam_url(2))
        self.textEditCar3Camurl_IR.setText(self.configMng.get_car_cam_url_ir(2))
        self.cbUnitEnable_3.setChecked(self.configMng.get_unit_enable(2))

        self.textEdit_detection_server_IP.setText(self.configMng.get_detection_server_ip())
        self.textEdit_detection_server_port.setText(str(self.configMng.get_detection_server_port()))
        self.cbEnableImgDetection.setChecked(self.configMng.get_detection_server_enable())

        # MMS(Mission Management Server) 설정
        self.lineEdit_MMS_IP.setText(self.configMng.get_MMS_ip())
        self.lineEdit_MMS_Port.setText(str(self.configMng.get_MMS_port()))
        
        self.btnBack.clicked.connect(self.onClick_btnBack)
        self.pushButton_saveSetup.clicked.connect(self.onClick_btnSaveSetup)
        
    def onClick_btnBack(self):
        print("onClick_btnBack")
        # self.closedSignal.emit()
        self.backSignal.emit()
        
    def closeEvent(self, event):
        print("closeEvent")
        self.closedSignal.emit()
        super().closeEvent(event)
    
    def onClick_btnSaveSetup(self):
        
        print("onClick_btnSaveSetup")
        car1ip = self.textEditCar1ip.toPlainText()
        car1port = self.textEditCar1port.toPlainText()
        carCamurl = self.textEditCar1Camurl.toPlainText()
        
        self.configMng.set_car_ip(car1ip)
        self.configMng.set_car_port(car1port)
        self.configMng.set_car_cam_url(carCamurl)
        self.configMng.set_car_cam_url_ir(self.textEditCar1Camurl_IR.toPlainText(),0)
        
        self.configMng.set_car_ip(self.textEditCar2ip.toPlainText(),1)
        self.configMng.set_car_port(self.textEditCar2port.toPlainText(),1)
        self.configMng.set_car_cam_url(self.textEditCar2Camurl.toPlainText(),1)
        self.configMng.set_car_cam_url_ir(self.textEditCar2Camurl_IR.toPlainText(),1)
        
        self.configMng.set_car_ip(self.textEditCar3ip.toPlainText(),2)
        self.configMng.set_car_port(self.textEditCar3port.toPlainText(),2)
        self.configMng.set_car_cam_url(self.textEditCar3Camurl.toPlainText(),2)
        self.configMng.set_car_cam_url_ir(self.textEditCar3Camurl_IR.toPlainText(),2)        
        
        self.configMng.set_detection_server_ip(self.textEdit_detection_server_IP.toPlainText())
        self.configMng.set_detection_server_port(self.textEdit_detection_server_port.toPlainText())
        self.configMng.set_detection_server_enable(self.cbEnableImgDetection.isChecked())

        self.configMng.set_unit_enable(self.cbUnitEnable_1.isChecked(), 0)
        self.configMng.set_unit_enable(self.cbUnitEnable_2.isChecked(), 1)
        self.configMng.set_unit_enable(self.cbUnitEnable_3.isChecked(), 2)

        self.configMng.set_MMS_ip(self.lineEdit_MMS_IP.text())
        self.configMng.set_MMS_port(self.lineEdit_MMS_Port.text())
        
        # 설정 파일 저장
        self.configMng.save_config()
        
        print("설정 저장 완료")
        
        # self.closedSignal.emit()
        self.backSignal.emit()  # 설정 저장 후 뒤로가기 신호 발생
        
if __name__ == '__main__':
    
    theApp = QApplication(sys.argv)
    form = setupForm()
    form.show()
    sys.exit(theApp.exec())
    
    