import sys
from PySide6.QtCore import QTimer, QRect, Qt
from PySide6.QtWidgets import QApplication,QWidget,QStackedWidget,QMessageBox

import startUpform ,mainForm ,setupForm



class MainForm(QWidget):
    def __init__(self):
        super().__init__()
        self.setGeometry(QRect(0, 0, 1920, 1080))
        self.setFixedSize(1920, 1080)
        self.setWindowState(Qt.WindowMaximized)
        
        #stackedWidget 만들고 
        self.stacked_widget = QStackedWidget(self)
        self.stacked_widget.setGeometry(0, 0, 1920, 1080)
        
        # 각 폼 인스턴스 생성
        self.startup_form = startUpform.setupForm(self)
        
        # 스택에 시작 폼 추가
        self.stacked_widget.addWidget(self.startup_form)
        
        # 초기 화면을 startup_form으로 설정
        self.stacked_widget.setCurrentWidget(self.startup_form)
        
        # 시그널 연결
        self.startup_form.btnStart.clicked.connect(self.show_main_form)
        self.startup_form.btnSetup.clicked.connect(self.show_setup_form)
        self.startup_form.btnExit.clicked.connect(self.close)

        

    def show_startup_form(self):
        
        try :
        
            # startup_form 빼고 나머지 위젯 제거
            while self.stacked_widget.count() > 1:
                widget = self.stacked_widget.widget(self.stacked_widget.count() - 1)
                self.stacked_widget.removeWidget(widget)
                widget.deleteLater()
            
            self.stacked_widget.setCurrentWidget(self.startup_form)
        except Exception as e:
            print(f'error occurred while removing widgets : {e}')

    def show_main_form(self):
        try:
            _form = mainForm.MainForm(self)
            _form.gotoHomeSignal.connect(self.show_startup_form)
            _form.gotoSetupSignal.connect(self.show_setup_form)
            
            self.stacked_widget.addWidget(_form)
            self.stacked_widget.setCurrentIndex(self.stacked_widget.currentIndex() + 1)
        except Exception as e:
            print(f'error occurred while showing main form : {e}')

    def show_setup_form(self):
        
        try :
            _form = setupForm.setupForm(self)
            # self._form.closedSignal.connect(self.backtotheStack)
            _form.backSignal.connect(self.navigateBack)
            self.stacked_widget.addWidget(_form)
            self.stacked_widget.setCurrentIndex(self.stacked_widget.currentIndex() + 1)
        except Exception as e:
            print(f'error occurred while showing setup form : {e}')
    
    def navigateBack(self,remove_current=True):
        
        # 이전 화면으로 이동
        """
        이전 위젯으로 이동하는 통합 메서드
        :param remove_current: 현재 위젯을 제거할지 여부
        """
        try :
            if self.stacked_widget.count() < 1:
                return
            current_index = self.stacked_widget.currentIndex()
            if current_index > 0:
                if remove_current:
                    current_widget = self.stacked_widget.currentWidget()
                    self.stacked_widget.removeWidget(current_widget)
                else:
                    self.stacked_widget.setCurrentIndex(current_index - 1)
        except Exception as e:
            print(f'error occurred while navigating back : {e}')
        
    def closeEvent(self, event):
        print("closeEvent")
        # 확인 대화상자를 표시하고 사용자가 Yes를 클릭하면 종료
        ret = QMessageBox.question(self, '종료 확인', '종료하시겠습니까?', QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if ret == QMessageBox.Yes:
            event.accept()
            super().closeEvent(event)
        else:
            event.ignore() # 이벤트 무시
        
        

if __name__ == '__main__':
    theApp = QApplication(sys.argv)
    form = MainForm()
    form.show()
    sys.exit(theApp.exec())