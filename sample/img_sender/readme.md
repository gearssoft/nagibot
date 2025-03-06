# img sender & receiver

## 사용법

**서버(receiver) 실행**
```bash
python detector.py
```

**클라이언트(sender) 실행**
```bash
python rtsp_img_sender.py
```

## 중요 code

**receiver 측 데이터 수신 코드**

```python
def _receive_numpy_array(self):
    """Receive a NumPy array over the socket connection using binary header"""
    self.connection.settimeout(1.0)
    header_size = 4 + 3*4 + 10  # 4 bytes for data_len, 3*4 for shape, 10 for dtype => 26 bytes
    header = self._recvall(header_size)
    if header is None:
        return None
    data_len, height, width, channels, dtype_bytes = struct.unpack("<L3I10s", header)
    dtype_str = dtype_bytes.decode('utf-8').strip('\x00')
    frame_data = self._recvall(data_len)
    if frame_data is None:
        return None
    frame = np.frombuffer(frame_data, dtype=dtype_str).reshape((height, width, channels))
    return frame
```

**sender측  송신 코드**

```python

def _stream_thread(self):
    """Main streaming thread function"""
    reconnect_delay = 5  # Seconds to wait before reconnecting
    if not self._connect_to_server():
        self.running = False
        return
    if not self._open_rtsp_stream():
        if self.client_socket:
            self.client_socket.close()
            self.client_socket = None
        self.connected = False
        self.connection_status.emit(False)
        self.running = False
        return
    self.status_update.emit("Starting to transmit frames...")
    self.frame_count = 0
    while self.running:
        ret, frame = self.cap.read()
        if not ret:
            self.status_update.emit("Failed to receive frame, attempting to reconnect...")
            self.cap.release()
            time.sleep(1)
            if not self._open_rtsp_stream():
                break
            continue
        self.last_frame = frame.copy()
        self.frame_captured.emit(frame)
        # Serialize the frame using binary header:
        frame_data = frame.tobytes()
        height, width, channels = frame.shape
        dtype_str = str(frame.dtype)
        # 고정 10바이트로 dtype 정보를 구성 (부족하면 null문자 채움)
        dtype_bytes = dtype_str.encode('utf-8')
        dtype_bytes = dtype_bytes.ljust(10, b'\0')[:10]
        data_len = len(frame_data)
        # 헤더 구성: <L3I10s => data_len, height, width, channels, dtype
        header = struct.pack("<L3I10s", data_len, height, width, channels, dtype_bytes)
        try:
            if self.client_socket:
                self.client_socket.sendall(header + frame_data)
                self.frame_count += 1
                self.frame_count_update.emit(self.frame_count)
                response = self._receive_detection_response()
                if response:
                    detections = response.get('detections', [])
                    self.current_detections = detections
                    self.detection_results.emit(detections)
        except socket.error as e:
            self.status_update.emit(f"Socket error: {e}")
            self.connected = False
            self.connection_status.emit(False)
            if self.client_socket:
                try:
                    self.client_socket.close()
                except:
                    pass
                self.client_socket = None
            time.sleep(reconnect_delay)
            if not self._connect_to_server():
                if not self.running:
                    break
                time.sleep(reconnect_delay)
                continue
    self.cleanup()
```

