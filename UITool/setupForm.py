import sys
from PySide6.QtWidgets import QApplication ,QWidget
from PySide6.QtCore import Signal

import UI.setupForm

class setupForm(QWidget,UI.setupForm.Ui_SetupForm):
    
    closedSignal = Signal()
    backSignal = Signal()
    
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setupUi(self)
        
        self.btnBack.clicked.connect(self.onClick_btnBack)
        
    def onClick_btnBack(self):
        print("onClick_btnBack")
        # self.closedSignal.emit()
        self.backSignal.emit()
        
    def closeEvent(self, event):
        print("closeEvent")
        self.closedSignal.emit()
        super().closeEvent(event)

if __name__ == '__main__':
    
    theApp = QApplication(sys.argv)
    form = setupForm()
    form.show()
    sys.exit(theApp.exec())
    
    