import sys
import socket
import struct
import pickle
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
    connection_status = Signal(str)
    client_connected = Signal(str)
    client_disconnected = Signal()
    frame_count_update = Signal(int)
    model_loaded = Signal(bool)
    
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
            self.load_model()
            
        self.running = True
        self.server_thread = threading.Thread(target=self._run_server)
        self.server_thread.daemon = True
        self.server_thread.start()
        
    def stop_server(self):
        """Stop the server and close all connections"""
        self.running = False
        # Close connection if exists
        if self.connection:
            self.connection.close()
            self.connection = None
        # Close server socket if exists
        if self.server_socket:
            self.server_socket.close()
            self.server_socket = None
        
        self.connection_status.emit("Server stopped")
        self.is_connected = False
        self.client_disconnected.emit()
        
    def _process_frame(self, frame):
        """Process frame with YOLO detection"""
        if self.model is None:
            self.connection_status.emit("YOLO model not loaded")
            return frame, []
            
        try:
            start_time = time.time()
            
            # Run YOLO detection
            results = self.model(frame)
            
            # Get processing time
            inference_time = time.time() - start_time
            self.inference_time.emit(inference_time)
            
            # Get detected objects
            detections = []
            for r in results:
                boxes = r.boxes
                for box in boxes:
                    # Get box coordinates
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
            
            # Draw bounding boxes on the image
            annotated_frame = results[0].plot()
            
            return annotated_frame, detections
            
        except Exception as e:
            self.connection_status.emit(f"Error in YOLO processing: {e}")
            return frame, []
        
    def _run_server(self):
        """Server main loop - runs in a separate thread"""
        try:
            # Create server socket
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(1)
            self.server_socket.settimeout(1.0)  # Add timeout to allow checking running flag
            
            self.connection_status.emit(f"Server started on {self.host}:{self.port}")
            
            while self.running:
                try:
                    # Wait for a connection
                    self.connection_status.emit("Waiting for connection...")
                    self.connection, self.client_address = self.server_socket.accept()
                    self.connection_status.emit(f"Connected to {self.client_address[0]}:{self.client_address[1]}")
                    self.client_connected.emit(f"{self.client_address[0]}:{self.client_address[1]}")
                    self.is_connected = True
                    self.frame_count = 0
                    
                    # Process the connection
                    while self.running and self.is_connected:
                        # Receive the NumPy array
                        try:
                            frame = self._receive_numpy_array()
                            if frame is not None:
                                
                                processed_frame, detections = self._process_frame(frame)
                                
                                self.frame_count += 1
                                self.frame_count_update.emit(self.frame_count)
                                self.image_received.emit(frame)
                                
                                #detection response , 프레임을 보낸 소켓에 응답해주기
                                # response = {
                                #     'frame': processed_frame,
                                #     'detections': detections
                                # }
                                
                            else:
                                # Connection closed by client
                                self.connection_status.emit("Connection closed by client")
                                self.is_connected = False
                                self.client_disconnected.emit()
                                break
                        except socket.timeout:
                            # Socket timeout - check if we should still be running
                            continue
                        except socket.error as e:
                            self.connection_status.emit(f"Socket error: {e}")
                            self.is_connected = False
                            self.client_disconnected.emit()
                            break
                        
                except socket.timeout:
                    # Server socket accept timeout - just continue the loop
                    continue
                except socket.error as e:
                    self.connection_status.emit(f"Server socket error: {e}")
                    time.sleep(1)  # Wait before trying to recreate the socket
                    
                    # Try to recreate the server socket
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
                            time.sleep(5)  # Wait longer before retrying
                
        except Exception as e:
            self.connection_status.emit(f"Server error: {e}")
        finally:
            # Clean up
            if self.connection:
                self.connection.close()
            if self.server_socket:
                self.server_socket.close()
            self.running = False
            self.is_connected = False
    
    def _receive_numpy_array(self):
        """Receive a NumPy array over the socket connection"""
        # Set a timeout to allow checking the running flag
        self.connection.settimeout(1.0)
        
        # First receive the message size (packed as a 4-byte long)
        msg_size_data = b''
        while len(msg_size_data) < 4:
            part = self.connection.recv(4 - len(msg_size_data))
            if not part:
                return None
            msg_size_data += part
        
        # Unpack the message size
        msg_size = struct.unpack(">L", msg_size_data)[0]
        
        # Now receive the actual serialized NumPy array
        data = b''
        while len(data) < msg_size:
            part = self.connection.recv(min(msg_size - len(data), 4096))
            if not part:
                return None
            data += part
        
        # Deserialize the NumPy array
        try:
            frame = pickle.loads(data)
            return frame
        except Exception as e:
            self.connection_status.emit(f"Error deserializing frame: {e}")
            return None


class MainWindow(QMainWindow):
    """Main application window"""
    def __init__(self):
        super().__init__()
        
        # Window setup
        self.setWindowTitle("RTSP Image Detector")
        self.resize(1000, 800)
        
        # Create main widget and layout
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        
        # Create control panel
        control_panel = QWidget()
        control_layout = QHBoxLayout(control_panel)
        
        # Start button
        self.start_button = QPushButton("Start Server")
        self.start_button.clicked.connect(self.start_server)
        control_layout.addWidget(self.start_button)
        
        # Stop button
        self.stop_button = QPushButton("Stop Server")
        self.stop_button.clicked.connect(self.stop_server)
        self.stop_button.setEnabled(False)
        control_layout.addWidget(self.stop_button)
        
        # Client status label
        self.client_status = QLabel("No client connected")
        self.client_status.setAlignment(Qt.AlignCenter)
        self.client_status.setFont(QFont("Arial", 10))
        self.client_status.setStyleSheet("color: gray;")
        control_layout.addWidget(self.client_status)
        
        # Frame count label
        self.frame_count_label = QLabel("Frames: 0")
        self.frame_count_label.setAlignment(Qt.AlignRight)
        control_layout.addWidget(self.frame_count_label)
        
        # Add control panel to main layout
        main_layout.addWidget(control_panel)
        
        # Create image display
        self.image_label = QLabel("No image received")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("background-color: black; color: white;")
        
        # Add image display to main layout
        main_layout.addWidget(self.image_label)
        
        # Set main widget
        self.setCentralWidget(main_widget)
        
        # Create status bar
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage("Server not started")
        
        # Create image receiver
        self.receiver = ImageReceiver(port=8085)
        self.receiver.connection_status.connect(self.update_status)
        self.receiver.image_received.connect(self.update_image)
        self.receiver.client_connected.connect(self.client_connected)
        self.receiver.client_disconnected.connect(self.client_disconnected)
        self.receiver.frame_count_update.connect(self.update_frame_count)
        self.receiver.model_loaded.connect(self.model_loaded)  
        
        # Add timestamp display refresh timer
        self.timestamp_label = QLabel("")
        self.statusBar.addPermanentWidget(self.timestamp_label)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_timestamp)
        self.timer.start(1000)  # Update every 1 second
        
        # Last updated timestamp
        self.last_update_time = None
        
    @Slot()
    def start_server(self):
        """Start the server"""
        self.receiver.start_server()
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        
    @Slot()
    def stop_server(self):
        """Stop the server"""
        self.receiver.stop_server()
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        
    @Slot(str)
    def update_status(self, message):
        """Update status bar message"""
        self.statusBar.showMessage(message)
        
    @Slot(str)
    def client_connected(self, client_info):
        """Update UI when client connects"""
        self.client_status.setText(f"Client: {client_info}")
        self.client_status.setStyleSheet("color: green; font-weight: bold;")
        
    @Slot()
    def client_disconnected(self):
        """Update UI when client disconnects"""
        self.client_status.setText("No client connected")
        self.client_status.setStyleSheet("color: gray;")
        
    @Slot(int)
    def update_frame_count(self, count):
        """Update frame counter"""
        self.frame_count_label.setText(f"Frames: {count}")
        
    @Slot(bool)
    def model_loaded(self, success):
        """Handle YOLO model loaded signal"""
        if success:
            self.statusBar.showMessage("YOLO model loaded successfully")
            print("YOLO model loaded successfully")
        else:
            print("Failed to load YOLO model")
            self.statusBar.showMessage("Failed to load YOLO model")
        
    @Slot(np.ndarray)
    def update_image(self, frame):
        """Update the image display with received frame"""
        # Convert the numpy array to a QImage
        height, width, channel = frame.shape
        bytes_per_line = 3 * width
        
        # Convert BGR (OpenCV format) to RGB (Qt format)
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Create QImage from the data
        q_img = QImage(rgb_frame.data, width, height, bytes_per_line, QImage.Format_RGB888)
        
        # Scale the image to fit the label, keeping aspect ratio
        pixmap = QPixmap.fromImage(q_img)
        scaled_pixmap = pixmap.scaled(self.image_label.size(), 
                                      Qt.KeepAspectRatio, 
                                      Qt.SmoothTransformation)
        
        # Update the image label
        self.image_label.setPixmap(scaled_pixmap)
        
        # Update last received timestamp
        self.last_update_time = datetime.now()
        
    @Slot()
    def update_timestamp(self):
        """Update the timestamp display"""
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
        """Handle window close event"""
        self.receiver.stop_server()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())