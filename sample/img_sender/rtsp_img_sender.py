import sys
import cv2
import numpy as np
import socket
import struct
import json
import time
import threading
import os
from datetime import datetime
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QPushButton, QLabel, QStatusBar, 
                               QLineEdit, QFormLayout, QGroupBox, QListWidget,
                               QSplitter)
from PySide6.QtCore import QTimer, Signal, Slot, QObject, Qt
from PySide6.QtGui import QImage, QPixmap, QFont, QCloseEvent

def save_config(rtsp_url, server_ip, server_port):
    """Save configuration to file"""
    config = {
        'rtsp_url': rtsp_url,
        'server_ip': server_ip,
        'server_port': server_port
    }
    try:
        with open('rtsp_sender_config.json', 'w') as f:
            json.dump(config, f)
    except Exception as e:
        print(f"Error saving config: {e}")

def load_config():
    """Load configuration from file"""
    default_config = {
        'rtsp_url': 'rtsp://192.168.4.62:554/stream_ch00_0',
        'server_ip': '127.0.0.1',
        'server_port': '8085'
    }
    try:
        if os.path.exists('rtsp_sender_config.json'):
            with open('rtsp_sender_config.json', 'r') as f:
                return json.load(f)
        return default_config
    except Exception as e:
        print(f"Error loading config: {e}")
        return default_config

class RtspSender(QObject):
    """Class to handle RTSP capture and TCP streaming in a separate thread"""
    status_update = Signal(str)
    frame_captured = Signal(np.ndarray)
    detection_results = Signal(list)
    frame_count_update = Signal(int)
    connection_status = Signal(bool)
    
    def __init__(self, rtsp_url="", server_ip="127.0.0.1", server_port=8085):
        super().__init__()
        self.rtsp_url = rtsp_url
        self.server_ip = server_ip
        self.server_port = server_port
        self.running = False
        self.connected = False
        self.cap = None
        self.client_socket = None
        self.thread = None
        self.frame_count = 0
        self.last_frame = None
        self.current_detections = []
        
    def start_streaming(self, rtsp_url=None, server_ip=None, server_port=None):
        """Start the streaming thread"""
        if rtsp_url:
            self.rtsp_url = rtsp_url
        if server_ip:
            self.server_ip = server_ip
        if server_port:
            self.server_port = int(server_port)
        if not self.rtsp_url:
            self.status_update.emit("Error: RTSP URL is required")
            return False
        if self.running:
            self.status_update.emit("Already running")
            return False
        self.running = True
        self.thread = threading.Thread(target=self._stream_thread)
        self.thread.daemon = True
        self.thread.start()
        return True
        
    def stop_streaming(self):
        """Stop the streaming thread"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)
        self.cleanup()
        self.status_update.emit("Streaming stopped")
        
    def cleanup(self):
        """Clean up resources"""
        if self.cap:
            try:
                self.cap.release()
            except:
                pass
            self.cap = None
        if self.client_socket:
            try:
                self.client_socket.close()
            except:
                pass
            self.client_socket = None
        self.connected = False
        self.connection_status.emit(False)
        
    def _connect_to_server(self):
        """Establish connection to the TCP server"""
        if self.client_socket:
            try:
                self.client_socket.close()
            except:
                pass
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.status_update.emit(f"Connecting to server at {self.server_ip}:{self.server_port}...")
            self.client_socket.connect((self.server_ip, self.server_port))
            self.connected = True
            self.connection_status.emit(True)
            self.status_update.emit("Connected to server successfully")
            return True
        except socket.error as e:
            self.status_update.emit(f"Connection failed: {e}")
            self.connected = False
            self.connection_status.emit(False)
            return False
    
    def _open_rtsp_stream(self):
        """Open the RTSP stream"""
        self.status_update.emit(f"Connecting to RTSP stream: {self.rtsp_url}")
        self.cap = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)
        if not self.cap.isOpened():
            self.status_update.emit("Failed to open RTSP stream")
            return False
        self.status_update.emit("RTSP stream opened successfully")
        return True
        
    def _receive_detection_response(self):
        """Receive detection results from the server (still using JSON)"""
        try:
            self.client_socket.settimeout(1.0)
            msg_size_data = b''
            while len(msg_size_data) < 4:
                part = self.client_socket.recv(4 - len(msg_size_data))
                if not part:
                    return None
                msg_size_data += part
            msg_size = struct.unpack("<L", msg_size_data)[0]
            data = b''
            while len(data) < msg_size:
                part = self.client_socket.recv(min(msg_size - len(data), 4096))
                if not part:
                    return None
                data += part
            response = json.loads(data.decode('utf-8'))
            return response
        except socket.error as e:
            self.status_update.emit(f"Error receiving detection response: {e}")
            return None
        except Exception as e:
            self.status_update.emit(f"Error processing detection response: {e}")
            return None
        
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

class MainWindow(QMainWindow):
    """Main application window"""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RTSP to TCP Sender with Detection Results")
        self.resize(1100, 800)
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        config = load_config()
        settings_group = QGroupBox("Connection Settings")
        settings_layout = QFormLayout(settings_group)
        self.rtsp_url_input = QLineEdit(config['rtsp_url'])
        self.rtsp_url_input.setMinimumWidth(400)  # 최소 너비를 400픽셀로 설정
        settings_layout.addRow("RTSP URL:", self.rtsp_url_input)
        self.server_ip_input = QLineEdit(config['server_ip'])
        settings_layout.addRow("Server IP:", self.server_ip_input)
        self.server_port_input = QLineEdit(str(config['server_port']))
        settings_layout.addRow("Server Port:", self.server_port_input)
        main_layout.addWidget(settings_group)
        splitter = QSplitter(Qt.Horizontal)
        video_panel = QWidget()
        video_layout = QVBoxLayout(video_panel)
        control_panel = QWidget()
        control_layout = QHBoxLayout(control_panel)
        self.start_button = QPushButton("Start Streaming")
        self.start_button.clicked.connect(self.start_streaming)
        control_layout.addWidget(self.start_button)
        self.stop_button = QPushButton("Stop Streaming")
        self.stop_button.clicked.connect(self.stop_streaming)
        self.stop_button.setEnabled(False)
        control_layout.addWidget(self.stop_button)
        self.connection_status = QLabel("Disconnected")
        self.connection_status.setAlignment(Qt.AlignCenter)
        self.connection_status.setFont(QFont("Arial", 10))
        self.connection_status.setStyleSheet("color: red; font-weight: bold;")
        control_layout.addWidget(self.connection_status)
        self.frame_count_label = QLabel("Frames: 0")
        self.frame_count_label.setAlignment(Qt.AlignRight)
        control_layout.addWidget(self.frame_count_label)
        video_layout.addWidget(control_panel)
        self.image_label = QLabel("No RTSP stream")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("background-color: black; color: white;")
        self.image_label.setMinimumSize(640, 480)
        video_layout.addWidget(self.image_label)
        detection_panel = QWidget()
        detection_layout = QVBoxLayout(detection_panel)
        detection_header = QLabel("Detection Results")
        detection_header.setFont(QFont("Arial", 12, QFont.Bold))
        detection_layout.addWidget(detection_header)
        self.detection_list = QListWidget()
        self.detection_list.setAlternatingRowColors(True)
        self.detection_list.setStyleSheet("font-size: 12px;")
        detection_layout.addWidget(self.detection_list)
        splitter.addWidget(video_panel)
        splitter.addWidget(detection_panel)
        splitter.setSizes([600, 300])
        main_layout.addWidget(splitter)
        self.setCentralWidget(main_widget)
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage("Ready")
        self.timestamp_label = QLabel("")
        self.statusBar.addPermanentWidget(self.timestamp_label)
        self.sender = RtspSender()
        self.sender.status_update.connect(self.update_status)
        self.sender.frame_captured.connect(self.update_preview)
        self.sender.frame_count_update.connect(self.update_frame_count)
        self.sender.connection_status.connect(self.update_connection_status)
        self.sender.detection_results.connect(self.update_detections)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_timestamp)
        self.timer.start(1000)
        self.last_update_time = None
        
    @Slot()
    def start_streaming(self):
        rtsp_url = self.rtsp_url_input.text().strip()
        server_ip = self.server_ip_input.text().strip()
        server_port = self.server_port_input.text().strip()
        if not rtsp_url:
            self.update_status("Error: RTSP URL is required")
            return
        save_config(rtsp_url, server_ip, server_port)
        if self.sender.start_streaming(rtsp_url, server_ip, server_port):
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(True)
            self.rtsp_url_input.setEnabled(False)
            self.server_ip_input.setEnabled(False)
            self.server_port_input.setEnabled(False)
        
    @Slot()
    def stop_streaming(self):
        self.sender.stop_streaming()
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.rtsp_url_input.setEnabled(True)
        self.server_ip_input.setEnabled(True)
        self.server_port_input.setEnabled(True)
        
    @Slot(str)
    def update_status(self, message):
        self.statusBar.showMessage(message)
        
    @Slot(bool)
    def update_connection_status(self, connected):
        if connected:
            self.connection_status.setText("Connected")
            self.connection_status.setStyleSheet("color: green; font-weight: bold;")
        else:
            self.connection_status.setText("Disconnected")
            self.connection_status.setStyleSheet("color: red; font-weight: bold;")
        
    @Slot(int)
    def update_frame_count(self, count):
        self.frame_count_label.setText(f"Frames: {count}")
        
    @Slot(list)
    def update_detections(self, detections):
        self.detection_list.clear()
        if not detections:
            self.detection_list.addItem("No objects detected")
        else:
            for i, obj in enumerate(detections):
                confidence = obj.get('confidence', 0) * 100
                name = obj.get('name', 'Unknown')
                box = obj.get('box', [0, 0, 0, 0])
                item_text = f"{i+1}. {name} ({confidence:.1f}%) at [{int(box[0])}, {int(box[1])}, {int(box[2])}, {int(box[3])}]"
                self.detection_list.addItem(item_text)
        
    @Slot(np.ndarray)
    def update_preview(self, frame, is_detection=False):
        display_frame = frame.copy()
        detections = self.sender.current_detections
        if detections and len(detections) > 0:
            for obj in detections:
                box = obj.get('box', None)
                name = obj.get('name', 'Unknown')
                confidence = obj.get('confidence', 0)
                if box:
                    x1, y1, x2, y2 = [int(coord) for coord in box]
                    cv2.rectangle(display_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    text = f"{name} {confidence*100:.1f}%"
                    (text_width, text_height), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                    cv2.rectangle(display_frame, (x1, y1 - 20), (x1 + text_width, y1), (0, 255, 0), -1)
                    cv2.putText(display_frame, text, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
        rgb_frame = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
        height, width, channel = rgb_frame.shape
        bytes_per_line = 3 * width
        q_img = QImage(rgb_frame.data, width, height, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(q_img)
        scaled_pixmap = pixmap.scaled(self.image_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.image_label.setPixmap(scaled_pixmap)
        if not is_detection:
            self.last_update_time = datetime.now()
        
    @Slot()
    def update_timestamp(self):
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if self.last_update_time:
            time_diff = (datetime.now() - self.last_update_time).total_seconds()
            if time_diff < 1:
                status = "Last frame: just now"
            else:
                status = f"Last frame: {time_diff:.1f}s ago"
        else:
            status = "No frames captured"
        self.timestamp_label.setText(f"{status} | {current_time}")
        
    def closeEvent(self, event: QCloseEvent):
        if self.sender.running:
            self.sender.stop_streaming()
            time.sleep(0.5)
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
