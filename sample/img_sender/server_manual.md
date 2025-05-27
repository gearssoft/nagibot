# YOLO Object Detection Server - Developer Manual

## 개요

YOLO 객체 감지 서버는 TCP 소켓을 통해 이미지를 받아 실시간 객체 감지를 수행하고 결과를 반환하는 서버입니다.

## 설치 및 요구사항

### 필수 패키지
```bash
pip install ultralytics opencv-python numpy
```

### 시스템 요구사항
- Python 3.8+
- CUDA (GPU 사용 시, 선택사항)
- 메모리: 최소 4GB RAM 권장

## 서버 실행

### 기본 실행
```bash
python server.py
```

### 고급 옵션
```bash
python server.py \
    --host 0.0.0.0 \
    --port 8085 \
    --model yolo11n.pt \
    --conf 0.25 \
    --log-level INFO
```

### 파라미터 설명
- `--host`: 서버 바인딩 주소 (기본값: 0.0.0.0)
- `--port`: 서버 포트 (기본값: 8085)
- `--model`: YOLO 모델 파일 경로 (기본값: yolo11n.pt)
- `--conf`: 신뢰도 임계값 (기본값: 0.25)
- `--log-level`: 로그 레벨 (DEBUG, INFO, WARNING, ERROR)

## 통신 프로토콜

### 연결 방식
- **프로토콜**: TCP
- **포트**: 8085 (기본값)
- **데이터 형식**: Binary + JSON

### 요청 흐름
1. 클라이언트가 서버에 TCP 연결
2. 이미지 데이터를 바이너리 형태로 전송
3. 서버가 YOLO 처리 후 JSON 응답 반환
4. 연결 유지하며 반복

## 클라이언트 구현

### 1. 이미지 전송 형식

이미지는 다음과 같은 바이너리 헤더로 전송됩니다:

```python
import struct
import numpy as np
import cv2

def send_image(socket, image):
    """이미지를 서버로 전송"""
    # 이미지를 uint8로 변환
    if image.dtype != np.uint8:
        image = image.astype(np.uint8)
    
    # 헤더 정보 준비
    height, width, channels = image.shape
    data = image.tobytes()
    data_len = len(data)
    dtype_str = str(image.dtype)
    dtype_bytes = dtype_str.encode('utf-8').ljust(10, b'\x00')
    
    # 헤더 패킹 (26 bytes)
    header = struct.pack("<L3I10s", data_len, height, width, channels, dtype_bytes)
    
    # 헤더 + 데이터 전송
    socket.sendall(header + data)
```

### 2. 응답 수신

```python
import json

def receive_response(socket):
    """서버 응답 수신"""
    # 메시지 크기 수신 (4 bytes)
    size_data = socket.recv(4)
    if not size_data:
        return None
    
    message_size = struct.unpack("<L", size_data)[0]
    
    # JSON 데이터 수신
    json_data = b''
    while len(json_data) < message_size:
        chunk = socket.recv(message_size - len(json_data))
        if not chunk:
            return None
        json_data += chunk
    
    # JSON 파싱
    response = json.loads(json_data.decode('utf-8'))
    return response
```

### 3. 완전한 클라이언트 예제

```python
import socket
import cv2
import json
import struct
import numpy as np

class YOLOClient:
    def __init__(self, host='localhost', port=8085):
        self.host = host
        self.port = port
        self.socket = None
    
    def connect(self):
        """서버에 연결"""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((self.host, self.port))
        print(f"서버에 연결됨: {self.host}:{self.port}")
    
    def disconnect(self):
        """연결 종료"""
        if self.socket:
            self.socket.close()
            self.socket = None
    
    def send_image(self, image):
        """이미지 전송"""
        if image.dtype != np.uint8:
            image = image.astype(np.uint8)
        
        height, width, channels = image.shape
        data = image.tobytes()
        data_len = len(data)
        dtype_str = str(image.dtype)
        dtype_bytes = dtype_str.encode('utf-8').ljust(10, b'\x00')
        
        header = struct.pack("<L3I10s", data_len, height, width, channels, dtype_bytes)
        self.socket.sendall(header + data)
    
    def receive_response(self):
        """응답 수신"""
        size_data = self.socket.recv(4)
        if not size_data:
            return None
        
        message_size = struct.unpack("<L", size_data)[0]
        
        json_data = b''
        while len(json_data) < message_size:
            chunk = self.socket.recv(message_size - len(json_data))
            if not chunk:
                return None
            json_data += chunk
        
        return json.loads(json_data.decode('utf-8'))
    
    def detect_objects(self, image):
        """객체 감지 요청"""
        self.send_image(image)
        return self.receive_response()

# 사용 예제
def main():
    client = YOLOClient('localhost', 8085)
    
    try:
        client.connect()
        
        # 웹캠에서 이미지 가져오기
        cap = cv2.VideoCapture(0)
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            # 객체 감지 요청
            result = client.detect_objects(frame)
            
            if result and result['detections']:
                print(f"감지된 객체 {len(result['detections'])}개:")
                for obj in result['detections']:
                    print(f"  - {obj['name']}: {obj['confidence']:.2f}")
            
            # ESC 키로 종료
            if cv2.waitKey(1) & 0xFF == 27:
                break
                
    except KeyboardInterrupt:
        print("종료합니다...")
    finally:
        client.disconnect()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
```

## 응답 형식

### JSON 응답 구조
```json
{
    "detections": [
        {
            "box": [x1, y1, x2, y2],
            "confidence": 0.85,
            "class": 0,
            "name": "person"
        }
    ],
    "timestamp": "2025-05-27T10:30:45.123456",
    "frame_count": 1234
}
```

### 필드 설명
- `detections`: 감지된 객체 배열
  - `box`: 바운딩 박스 좌표 [x1, y1, x2, y2]
  - `confidence`: 신뢰도 (0.0 ~ 1.0)
  - `class`: 클래스 ID
  - `name`: 클래스 이름
- `timestamp`: 처리 시간 (ISO 8601 형식)
- `frame_count`: 현재 세션의 프레임 카운트

## 다양한 언어별 클라이언트 예제

### JavaScript (Node.js)
```javascript
const net = require('net');
const fs = require('fs');

class YOLOClient {
    constructor(host = 'localhost', port = 8085) {
        this.host = host;
        this.port = port;
        this.socket = null;
    }
    
    connect() {
        return new Promise((resolve, reject) => {
            this.socket = net.createConnection(this.port, this.host);
            this.socket.on('connect', resolve);
            this.socket.on('error', reject);
        });
    }
    
    sendImageFile(imagePath) {
        // 이미지 파일을 OpenCV로 처리 후 전송하는 로직 구현
        // (실제로는 sharp 등의 라이브러리 사용 권장)
    }
}
```

### Python (asyncio 버전)
```python
import asyncio
import cv2
import json
import struct

class AsyncYOLOClient:
    def __init__(self, host='localhost', port=8085):
        self.host = host
        self.port = port
        self.reader = None
        self.writer = None
    
    async def connect(self):
        self.reader, self.writer = await asyncio.open_connection(
            self.host, self.port
        )
    
    async def send_image(self, image):
        # 이미지 전송 로직 (위와 동일)
        pass
    
    async def receive_response(self):
        # 응답 수신 로직 (위와 동일하지만 async/await 사용)
        pass
```

## 성능 최적화

### 서버 측 최적화
1. **GPU 사용**: CUDA 설치 시 자동으로 GPU 가속 사용
2. **모델 선택**: 
   - `yolo11n.pt`: 가장 빠름, 정확도 낮음
   - `yolo11s.pt`: 균형잡힌 성능
   - `yolo11m.pt`: 높은 정확도
   - `yolo11l.pt`, `yolo11x.pt`: 최고 정확도, 느림

### 클라이언트 측 최적화
1. **이미지 크기 조정**: 큰 이미지는 리사이즈 후 전송
2. **압축**: JPEG 압축 후 전송 (정확도 vs 속도 트레이드오프)
3. **배치 처리**: 여러 이미지를 한 번에 처리 (향후 지원 예정)

## 에러 처리

### 일반적인 오류 상황
1. **연결 오류**: 서버가 실행되지 않음
2. **모델 로드 실패**: 모델 파일이 존재하지 않음
3. **메모리 부족**: 이미지가 너무 크거나 메모리 부족
4. **타임아웃**: 네트워크 지연 또는 서버 과부하

### 오류 처리 예제
```python
try:
    client.connect()
    result = client.detect_objects(image)
except ConnectionRefusedError:
    print("서버에 연결할 수 없습니다. 서버가 실행 중인지 확인하세요.")
except socket.timeout:
    print("서버 응답 타임아웃")
except Exception as e:
    print(f"예상치 못한 오류: {e}")
```

## 모니터링 및 로깅

### 서버 로그
- **파일**: `yolo_server.log`
- **레벨**: DEBUG, INFO, WARNING, ERROR
- **내용**: 연결 상태, 처리 성능, 오류 정보

### 성능 메트릭
- FPS (Frames Per Second)
- 평균 추론 시간
- 메모리 사용량
- 감지된 객체 수

## 배포 및 운영

### Docker 배포
```dockerfile
FROM python:3.9-slim

RUN apt-get update && apt-get install -y \
    libglib2.0-0 libsm6 libxext6 libxrender-dev libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY detector_server.py .
COPY yolo11n.pt .

EXPOSE 8085
CMD ["python", "detector_server.py", "--host", "0.0.0.0"]
```

### systemd 서비스
```ini
[Unit]
Description=YOLO Object Detection Server
After=network.target

[Service]
Type=simple
User=yolo
Group=yolo
WorkingDirectory=/opt/yolo-server
ExecStart=/usr/bin/python3 detector_server.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

## 문제 해결

### FAQ

**Q: 서버가 시작되지 않습니다.**
A: 포트가 이미 사용 중인지 확인하고, 방화벽 설정을 점검하세요.

**Q: 감지 성능이 낮습니다.**
A: `--conf` 값을 낮춰보거나, 더 큰 모델을 사용해보세요.

**Q: 메모리 부족 오류가 발생합니다.**
A: 이미지 크기를 줄이거나, 더 작은 모델(yolo11n.pt)을 사용하세요.

**Q: GPU를 사용하고 있는지 확인하는 방법은?**
A: 서버 시작 시 로그에서 CUDA 사용 여부를 확인할 수 있습니다.

### 디버깅 팁
1. `--log-level DEBUG`로 상세 로그 확인
2. `nvidia-smi`로 GPU 사용률 모니터링
3. `htop`으로 CPU/메모리 사용률 확인
4. `netstat -tlnp | grep 8085`로 포트 상태 확인

## 라이선스 및 제한사항

- YOLO 모델은 AGPL-3.0 라이선스를 따릅니다
- 상업적 사용 시 Ultralytics 라이선스 정책을 확인하세요
- 서버는 단일 클라이언트 연결만 지원합니다 (동시 연결 불가)

## 지원 및 문의

- GitHub Issues: [프로젝트 저장소]
- 이메일: [개발자 이메일]
- 문서 업데이트: [문서 저장소]