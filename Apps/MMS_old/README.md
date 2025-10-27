# 주차관제 Agent 개발 페이지

## setup

**.env 파일 생성 예**<br />
```env
ip=0.tcp.jp.ngrok.io
port=19888
APP=client
```

## 실행

```bash
# 서버 실행
python -m server.app

pm2 start "python -m server.app" --name parkingEyeServer
```

## 문서

[프로잭트 문서](https://docs.google.com/document/d/1NrkzzD0N6o6-OJrknLC4_QN35U3kYk3KM71BzrA1Ovg/edit?tab=t.4y1vtj8q3w6n)