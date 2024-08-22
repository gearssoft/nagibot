import sys
from PySide6.QtWidgets import QApplication ,QWidget
from PySide6.QtCore import Signal

import UI.StartUpForm

class setupForm(QWidget,UI.StartUpForm.Ui_StartUpForm):
    
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setupUi(self)
        
        self.btnStart.clicked.connect(self.gotoMain)
        self.btnSetup.clicked.connect(self.gotoSetup)
        self.btnExit.clicked.connect(self.gotoExit)
        
    
    def gotoMain(self):
        print("gotoMain")
    
    def gotoSetup(self):
        print("gotoSetup")
    
    def gotoExit(self):
        print("gotoExit")
    
        

if __name__ == '__main__':
    
    theApp = QApplication(sys.argv)
    form = setupForm()
    form.show()
    sys.exit(theApp.exec())
    
    