# 수륙양용 로봇 관제 시스템 UI Application

## 개발환경

```bash
pip install -r requirements.txt
``` 

**designer**
```bash
pyside6-designer
```
## ui 파일 변환

uic 커맨드를 사용하여 ui 파일을 py로 변환합니다. 아래 예제 를 참고 하세요.

```bash
pyside6-uic mainwindow.ui -o mainwindow.py
```

## qrc 파일 변환

qrc 파일을 py로 변환합니다. 아래 예제를 참고 하세요.

```bash
pyside6-rcc assets/icons.qrc -o icons_rc.py
```