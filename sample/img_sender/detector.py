import sys
import socket
import struct
import json
import numpy as np
import cv2
import threading
import time
from datetime import datetime
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QPushButton, QLabel, QStatusBar)
from PySide6.QtCore import QTimer, Signal, Slot, QObject, Qt
from PySide6.QtGui import QImage, QPixmap, QFont

# Import YOLO
from ultralytics import YOLO

class ImageReceiver(QObject):
    """Class to handle receiving images over TCP in a separate thread"""
    image_received = Signal(np.ndarray)
    processed_image = Signal(np.ndarray, list)
    connection_status = Signal(str)
    client_connected = Signal(str)
    client_disconnected = Signal()
    frame_count_update = Signal(int)
    model_loaded = Signal(bool)
    inference_time = Signal(float)
    
    def __init__(self, host='0.0.0.0', port=8085):
        super().__init__()
        self.host = host
        self.port = port
        self.server_socket = None
        self.connection = None
        self.client_address = None
        self.running = False
        self.frame_count = 0
        self.is_connected = False
        
        self.model = None
        self.model_path = "yolo11n.pt"
        self.conf_threshold = 0.25
        self.enable_processing = True
        
    def load_model(self, model_path=None):
        """Load the YOLO model"""
        if model_path:
            self.model_path = model_path
        try:
            self.connection_status.emit(f"Loading YOLO model from {self.model_path}...")
            self.model = YOLO(self.model_path)
            self.connection_status.emit("YOLO model loaded successfully")
            self.model_loaded.emit(True)
            return True
        except Exception as e:
            self.connection_status.emit(f"Failed to load YOLO model: {e}")
            self.model_loaded.emit(False)
            return False
    
    def start_server(self):
        """Start the TCP server in a separate thread"""
        if self.running:
            return
        if self.model is None:
            if not self.load_model():
                return
        self.running = True
        self.server_thread = threading.Thread(target=self._run_server)
        self.server_thread.daemon = True
        self.server_thread.start()
        
    def stop_server(self):
        """Stop the server and close all connections"""
        self.running = False
        if self.connection:
            try:
                self.connection.close()
            except:
                pass
            self.connection = None
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
            self.server_socket = None
        self.connection_status.emit("Server stopped")
        self.is_connected = False
        self.client_disconnected.emit()
        
    def _process_frame(self, frame):
        """Process frame with YOLO detection"""
        if not self.enable_processing or self.model is None:
            return frame, []
        try:
            start_time = time.time()
            results = self.model(frame, conf=self.conf_threshold)
            inference_time = time.time() - start_time
            self.inference_time.emit(inference_time)
            detections = []
            for r in results:
                boxes = r.boxes
                for box in boxes:
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    conf = box.conf[0].item()
                    cls = int(box.cls[0].item())
                    name = r.names[cls]
                    detections.append({
                        'box': [float(x1), float(y1), float(x2), float(y2)],
                        'confidence': float(conf),
                        'class': cls,
                        'name': name
                    })
            annotated_frame = results[0].plot()
            return annotated_frame, detections
        except Exception as e:
            self.connection_status.emit(f"Error in YOLO processing: {e}")
            return frame, []
            
    def _send_detection_response(self, connection, detections, processed_frame=None):
        """Send detection results back to the client (remains JSON-based)"""
        try:
            response = {
                'detections': detections,
            }
            response_json = json.dumps(response).encode('utf-8')
            message_size = struct.pack("<L", len(response_json))
            connection.sendall(message_size + response_json)
            self.connection_status.emit(f"Sent detection results with {len(detections)} objects")
            return True
        except socket.error as e:
            self.connection_status.emit(f"Error sending detection response: {e}")
            return False

    def _recvall(self, n):
        """Helper function to receive n bytes or return None if connection closed"""
        data = b''
        while len(data) < n:
            packet = self.connection.recv(n - len(data))
            if not packet:
                return None
            data += packet
        return data

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

    def _run_server(self):
        """Server main loop - runs in a separate thread"""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(1)
            self.server_socket.settimeout(1.0)
            self.connection_status.emit(f"Server started on {self.host}:{self.port}")
            while self.running:
                try:
                    self.connection_status.emit("Waiting for connection...")
                    self.connection, self.client_address = self.server_socket.accept()
                    self.connection_status.emit(f"Connected to {self.client_address[0]}:{self.client_address[1]}")
                    self.client_connected.emit(f"{self.client_address[0]}:{self.client_address[1]}")
                    self.is_connected = True
                    self.frame_count = 0
                    while self.running and self.is_connected:
                        try:
                            frame = self._receive_numpy_array()
                            if frame is not None:
                                self.frame_count += 1
                                self.frame_count_update.emit(self.frame_count)
                                processed_frame, detections = self._process_frame(frame)
                                self.image_received.emit(processed_frame)
                                self.processed_image.emit(processed_frame, detections)
                                self._send_detection_response(self.connection, detections)
                            else:
                                self.connection_status.emit("Connection closed by client")
                                self.is_connected = False
                                self.client_disconnected.emit()
                                break
                        except socket.timeout:
                            continue
                        except socket.error as e:
                            self.connection_status.emit(f"Socket error: {e}")
                            self.is_connected = False
                            self.client_disconnected.emit()
                            break
                except socket.timeout:
                    continue
                except socket.error as e:
                    self.connection_status.emit(f"Server socket error: {e}")
                    time.sleep(1)
                    if self.running:
                        try:
                            if self.server_socket:
                                self.server_socket.close()
                            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                            self.server_socket.bind((self.host, self.port))
                            self.server_socket.listen(1)
                            self.server_socket.settimeout(1.0)
                        except Exception as e:
                            self.connection_status.emit(f"Failed to recreate server socket: {e}")
                            time.sleep(5)
        except Exception as e:
            self.connection_status.emit(f"Server error: {e}")
        finally:
            if self.connection:
                try:
                    self.connection.close()
                except:
                    pass
            if self.server_socket:
                try:
                    self.server_socket.close()
                except:
                    pass
            self.running = False
            self.is_connected = False

class MainWindow(QMainWindow):
    """Main application window"""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("YOLO Object Detection Server")
        self.resize(1000, 800)
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        control_panel = QWidget()
        control_layout = QHBoxLayout(control_panel)
        self.start_button = QPushButton("Start Server")
        self.start_button.clicked.connect(self.start_server)
        control_layout.addWidget(self.start_button)
        self.stop_button = QPushButton("Stop Server")
        self.stop_button.clicked.connect(self.stop_server)
        self.stop_button.setEnabled(False)
        control_layout.addWidget(self.stop_button)
        self.client_status = QLabel("No client connected")
        self.client_status.setAlignment(Qt.AlignCenter)
        self.client_status.setFont(QFont("Arial", 10))
        self.client_status.setStyleSheet("color: gray;")
        control_layout.addWidget(self.client_status)
        self.frame_count_label = QLabel("Frames: 0")
        self.frame_count_label.setAlignment(Qt.AlignRight)
        control_layout.addWidget(self.frame_count_label)
        main_layout.addWidget(control_panel)
        model_panel = QWidget()
        model_layout = QHBoxLayout(model_panel)
        self.model_status_label = QLabel("Model: Not loaded")
        model_layout.addWidget(self.model_status_label)
        self.inference_time_label = QLabel("Inference: - ms")
        self.inference_time_label.setAlignment(Qt.AlignRight)
        model_layout.addWidget(self.inference_time_label)
        main_layout.addWidget(model_panel)
        self.image_label = QLabel("No image received")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("background-color: black; color: white;")
        main_layout.addWidget(self.image_label)
        self.detections_label = QLabel("Detected objects will appear here")
        self.detections_label.setWordWrap(True)
        self.detections_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.detections_label.setMinimumHeight(100)
        self.detections_label.setStyleSheet("background-color: #f0f0f0; padding: 10px; border-radius: 5px;")
        main_layout.addWidget(self.detections_label)
        self.setCentralWidget(main_widget)
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage("Server not started")
        self.receiver = ImageReceiver(port=8085)
        self.receiver.connection_status.connect(self.update_status)
        self.receiver.image_received.connect(self.update_image)
        self.receiver.processed_image.connect(self.update_processed_image)
        self.receiver.client_connected.connect(self.client_connected)
        self.receiver.client_disconnected.connect(self.client_disconnected)
        self.receiver.frame_count_update.connect(self.update_frame_count)
        self.receiver.model_loaded.connect(self.model_loaded)
        self.receiver.inference_time.connect(self.update_inference_time)
        self.timestamp_label = QLabel("")
        self.statusBar.addPermanentWidget(self.timestamp_label)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_timestamp)
        self.timer.start(1000)
        self.last_update_time = None
        
    @Slot()
    def start_server(self):
        self.receiver.start_server()
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        
    @Slot()
    def stop_server(self):
        self.receiver.stop_server()
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        
    @Slot(str)
    def update_status(self, message):
        self.statusBar.showMessage(message)
        
    @Slot(str)
    def client_connected(self, client_info):
        self.client_status.setText(f"Client: {client_info}")
        self.client_status.setStyleSheet("color: green; font-weight: bold;")
        
    @Slot()
    def client_disconnected(self):
        self.client_status.setText("No client connected")
        self.client_status.setStyleSheet("color: gray;")
        
    @Slot(int)
    def update_frame_count(self, count):
        self.frame_count_label.setText(f"Frames: {count}")
        
    @Slot(bool)
    def model_loaded(self, success):
        if success:
            self.model_status_label.setText("Model: Loaded")
            self.model_status_label.setStyleSheet("color: green;")
        else:
            self.model_status_label.setText("Model: Failed to load")
            self.model_status_label.setStyleSheet("color: red;")
            
    @Slot(float)
    def update_inference_time(self, time_seconds):
        self.inference_time_label.setText(f"Inference: {time_seconds*1000:.1f} ms")
        
    @Slot(np.ndarray)
    def update_image(self, frame):
        height, width, channel = frame.shape
        bytes_per_line = 3 * width
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        q_img = QImage(rgb_frame.data, width, height, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(q_img)
        scaled_pixmap = pixmap.scaled(self.image_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.image_label.setPixmap(scaled_pixmap)
        self.last_update_time = datetime.now()
        
    @Slot(np.ndarray, list)
    def update_processed_image(self, frame, detections):
        if not detections:
            self.detections_label.setText("No objects detected")
        else:
            detection_text = f"Detected {len(detections)} objects:\n"
            for i, obj in enumerate(detections[:10]):
                detection_text += f"{i+1}. {obj['name']} ({obj['confidence']:.2f})\n"
            if len(detections) > 10:
                detection_text += f"... and {len(detections)-10} more"
            self.detections_label.setText(detection_text)
        
    @Slot()
    def update_timestamp(self):
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if self.last_update_time:
            time_diff = (datetime.now() - self.last_update_time).total_seconds()
            if time_diff < 5:
                status = "Last frame: just now"
            else:
                status = f"Last frame: {time_diff:.1f}s ago"
        else:
            status = "No frames received"
        self.timestamp_label.setText(f"{status} | {current_time}")
        
    def closeEvent(self, event):
        self.receiver.stop_server()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
