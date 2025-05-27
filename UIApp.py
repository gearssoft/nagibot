from PySide6.QtWidgets import QApplication
import sys

from UITool.app import MainForm

def main():
    theApp = QApplication(sys.argv)
    form = MainForm()
    form.show()
    sys.exit(theApp.exec())