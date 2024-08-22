import sys
from PySide6.QtWidgets import QApplication ,QWidget
from PySide6.QtCore import Signal

# import icons_rc
import UI.mainForm

class MainForm(QWidget,UI.mainForm.Ui_mainForm):
    
    gotoHomeSignal = Signal()  # 새로운 시그널 추가
    gotoSetupSignal = Signal()
    closedSignal = Signal()
    
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setupUi(self)
        
        self.btnGoHome.clicked.connect(self.gotoHome)
        self.btnGotoSetup.clicked.connect(self.gotoSetup)
        
    def gotoHome(self):
        print("gotoHome")
        # startup form으로 이동
        self.gotoHomeSignal.emit()
        
    def gotoSetup(self):
        print("gotoSetup")
        # setup form으로 이동
        self.gotoSetupSignal.emit()
        
    def closeEvent(self, event):
        print("closeEvent")
        # if self.parent() is not None:
        #     self.parent().close()
        self.closedSignal.emit()
        
        super().closeEvent(event)

        
if __name__ == '__main__':
    
    theApp = QApplication(sys.argv)
    form = MainForm()
    form.show()
    sys.exit(theApp.exec())
