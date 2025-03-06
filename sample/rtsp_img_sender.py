import sys
import cv2
import numpy as np
import socket
import pickle
import struct
import time
import threading
from datetime import datetime
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                              QHBoxLayout, QPushButton, QLabel, QStatusBar, 
                              QLineEdit, QFormLayout, QGroupBox)
from PySide6.QtCore import QTimer, Signal, Slot, QObject, Qt
from PySide6.QtGui import QImage, QPixmap, QFont, QIcon, QCloseEvent

class RtspSender(QObject):
    """Class to handle RTSP capture and TCP streaming in a separate thread"""
    status_update = Signal(str)
    frame_captured = Signal(np.ndarray)
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
            self.cap.release()
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
        
        # OpenCV's VideoCapture for RTSP
        self.cap = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)
        
        # Check if the connection was successful
        if not self.cap.isOpened():
            self.status_update.emit("Failed to open RTSP stream")
            return False
        
        self.status_update.emit("RTSP stream opened successfully")
        return True
        
    def _stream_thread(self):
        """Main streaming thread function"""
        reconnect_delay = 5  # Seconds to wait before reconnecting
        
        # Open RTSP stream
        if not self._open_rtsp_stream():
            self.client_socket.close()
            self.client_socket = None
            self.connected = False
            self.connection_status.emit(False)
            self.running = False
            return
            
        
        # Connect to TCP server
        if not self._connect_to_server():
            self.running = False
            return
            
        
        self.status_update.emit("Starting to transmit frames...")
        self.frame_count = 0
        
        while self.running:
            # Read frame from RTSP stream
            ret, frame = self.cap.read()
            
            if not ret:
                self.status_update.emit("Failed to receive frame, attempting to reconnect...")
                self.cap.release()
                time.sleep(1)
                if not self._open_rtsp_stream():
                    break
                continue
                
            # Send frame to UI for preview
            self.frame_captured.emit(frame)
            
            # Serialize the numpy array
            data = pickle.dumps(frame)
            
            # Send the size of the serialized data first
            message_size = struct.pack(">L", len(data))
            
            try:
                # Send the message size followed by the serialized frame
                if self.client_socket:
                    self.client_socket.sendall(message_size + data)
                    
                    self.frame_count += 1
                    self.frame_count_update.emit(self.frame_count)
                    
            except socket.error as e:
                self.status_update.emit(f"Socket error: {e}")
                self.connected = False
                self.connection_status.emit(False)
                
                # Try to reconnect to server
                if self.client_socket:
                    try:
                        self.client_socket.close()
                    except:
                        pass
                    self.client_socket = None
                    
                time.sleep(reconnect_delay)
                if not self._connect_to_server():
                    if not self.running:  # Check if we're still supposed to be running
                        break
                    time.sleep(reconnect_delay)
                    continue
        
        # Clean up resources
        self.cleanup()


class MainWindow(QMainWindow):
    """Main application window"""
    def __init__(self):
        super().__init__()
        
        # Window setup
        self.setWindowTitle("RTSP to TCP Sender")
        self.resize(800, 700)
        
        # Create main widget and layout
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        
        # Create settings group
        settings_group = QGroupBox("Connection Settings")
        settings_layout = QFormLayout(settings_group)
        
        # RTSP URL input
        self.rtsp_url_input = QLineEdit("rtsp://admin:71021707@gears001.iptime.org:6554/stream_ch00_0")
        settings_layout.addRow("RTSP URL:", self.rtsp_url_input)
        
        # Server IP input
        self.server_ip_input = QLineEdit("127.0.0.1")
        settings_layout.addRow("Server IP:", self.server_ip_input)
        
        # Server Port input
        self.server_port_input = QLineEdit("8085")
        settings_layout.addRow("Server Port:", self.server_port_input)
        
        # Add settings group to main layout
        main_layout.addWidget(settings_group)
        
        # Create control panel
        control_panel = QWidget()
        control_layout = QHBoxLayout(control_panel)
        
        # Start button
        self.start_button = QPushButton("Start Streaming")
        self.start_button.clicked.connect(self.start_streaming)
        control_layout.addWidget(self.start_button)
        
        # Stop button
        self.stop_button = QPushButton("Stop Streaming")
        self.stop_button.clicked.connect(self.stop_streaming)
        self.stop_button.setEnabled(False)
        control_layout.addWidget(self.stop_button)
        
        # Connection status label
        self.connection_status = QLabel("Disconnected")
        self.connection_status.setAlignment(Qt.AlignCenter)
        self.connection_status.setFont(QFont("Arial", 10))
        self.connection_status.setStyleSheet("color: red; font-weight: bold;")
        control_layout.addWidget(self.connection_status)
        
        # Frame count label
        self.frame_count_label = QLabel("Frames: 0")
        self.frame_count_label.setAlignment(Qt.AlignRight)
        control_layout.addWidget(self.frame_count_label)
        
        # Add control panel to main layout
        main_layout.addWidget(control_panel)
        
        # Create image display
        self.image_label = QLabel("No RTSP stream")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("background-color: black; color: white;")
        
        # Add image display to main layout
        main_layout.addWidget(self.image_label)
        
        # Set main widget
        self.setCentralWidget(main_widget)
        
        # Create status bar
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage("Ready")
        
        # Add timestamp display
        self.timestamp_label = QLabel("")
        self.statusBar.addPermanentWidget(self.timestamp_label)
        
        # Create RTSP sender
        self.sender = RtspSender()
        self.sender.status_update.connect(self.update_status)
        self.sender.frame_captured.connect(self.update_preview)
        self.sender.frame_count_update.connect(self.update_frame_count)
        self.sender.connection_status.connect(self.update_connection_status)
        
        # Add timestamp update timer
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_timestamp)
        self.timer.start(1000)  # Update every 1 second
        
        # Last updated timestamp
        self.last_update_time = None
        
    @Slot()
    def start_streaming(self):
        """Start streaming RTSP to TCP"""
        rtsp_url = self.rtsp_url_input.text().strip()
        server_ip = self.server_ip_input.text().strip()
        server_port = self.server_port_input.text().strip()
        
        if not rtsp_url:
            self.update_status("Error: RTSP URL is required")
            return
            
        if self.sender.start_streaming(rtsp_url, server_ip, server_port):
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(True)
            self.rtsp_url_input.setEnabled(False)
            self.server_ip_input.setEnabled(False)
            self.server_port_input.setEnabled(False)
        
    @Slot()
    def stop_streaming(self):
        """Stop streaming"""
        self.sender.stop_streaming()
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.rtsp_url_input.setEnabled(True)
        self.server_ip_input.setEnabled(True)
        self.server_port_input.setEnabled(True)
        
    @Slot(str)
    def update_status(self, message):
        """Update status bar message"""
        self.statusBar.showMessage(message)
        
    @Slot(bool)
    def update_connection_status(self, connected):
        """Update connection status display"""
        if connected:
            self.connection_status.setText("Connected")
            self.connection_status.setStyleSheet("color: green; font-weight: bold;")
        else:
            self.connection_status.setText("Disconnected")
            self.connection_status.setStyleSheet("color: red; font-weight: bold;")
        
    @Slot(int)
    def update_frame_count(self, count):
        """Update frame counter"""
        self.frame_count_label.setText(f"Frames: {count}")
        
    @Slot(np.ndarray)
    def update_preview(self, frame):
        """Update the preview image with current frame"""
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
            if time_diff < 1:
                status = "Last frame: just now"
            else:
                status = f"Last frame: {time_diff:.1f}s ago"
        else:
            status = "No frames captured"
            
        self.timestamp_label.setText(f"{status} | {current_time}")
        
    def closeEvent(self, event: QCloseEvent):
        """Handle window close event - ensure clean shutdown"""
        # Stop the streaming thread
        if self.sender.running:
            self.sender.stop_streaming()
            # Give it a moment to clean up
            time.sleep(0.5)
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())