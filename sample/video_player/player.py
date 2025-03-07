import sys
import cv2
import time
from PySide6.QtWidgets import (QApplication, QMainWindow, QPushButton, QVBoxLayout, 
                               QHBoxLayout, QWidget, QLabel, QLineEdit)
from PySide6.QtCore import QThread, Signal, QTimer, Qt
from PySide6.QtGui import QImage, QPixmap

class VideoThread(QThread):
    frame_ready = Signal(object)
    error = Signal(str)
    
    def __init__(self, url):
        super().__init__()
        self.url = url
        self.running = False
        self.cap = None
        
    def run(self):
        self.running = True
        
        try:
            self.cap = cv2.VideoCapture(self.url)
            if not self.cap.isOpened():
                self.error.emit(f"Failed to open: {self.url}")
                self.running = False
                return
                
            while self.running:
                ret, frame = self.cap.read()
                if not ret:
                    # Handle transient errors by retrying a few times
                    retry_count = 0
                    max_retries = 5
                    
                    while retry_count < max_retries and self.running:
                        time.sleep(0.5)  # Short delay before retry
                        ret, frame = self.cap.read()
                        if ret:
                            break
                        retry_count += 1
                    
                    if not ret:
                        self.error.emit("Stream error, reconnecting...")
                        # Reopen the stream
                        if self.cap and self.cap.isOpened():
                            self.cap.release()
                        self.cap = cv2.VideoCapture(self.url)
                        if not self.cap.isOpened():
                            self.error.emit(f"Failed to reconnect: {self.url}")
                            self.running = False
                            break
                        continue
                
                # Convert frame to RGB
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                self.frame_ready.emit(frame_rgb)
                
                # Add a small delay to avoid overwhelming the GUI thread
                time.sleep(0.01)
                
        except Exception as e:
            self.error.emit(f"Error in video thread: {str(e)}")
        finally:
            if self.cap and self.cap.isOpened():
                self.cap.release()
                
    def stop(self):
        self.running = False
        self.wait()  # Wait for the thread to finish


class VideoPlayer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PySide6 Video Player")
        self.setGeometry(100, 100, 800, 600)
        
        # Main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        
        # Protocol support message
        protocol_label = QLabel("Supported streaming protocols: RTSP, RTMP, HTTP(S), M3U8/HLS")
        protocol_label.setStyleSheet("color: #666; font-style: italic;")
        main_layout.addWidget(protocol_label)
        
        # URL input area
        url_layout = QHBoxLayout()
        url_label = QLabel("URL:")
        self.url_input = QLineEdit()
        self.url_input.setText("http://210.99.70.120:1935/live/cctv001.stream/playlist.m3u8")
        url_layout.addWidget(url_label)
        url_layout.addWidget(self.url_input)
        main_layout.addLayout(url_layout)
        
        # Video display area with status overlay
        video_container = QWidget()
        video_layout = QVBoxLayout(video_container)
        video_layout.setContentsMargins(0, 0, 0, 0)
        
        self.video_label = QLabel()
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setMinimumSize(640, 480)
        self.video_label.setStyleSheet("background-color: black;")
        
        self.status_overlay = QLabel("Ready")
        self.status_overlay.setAlignment(Qt.AlignCenter)
        self.status_overlay.setStyleSheet("""
            background-color: rgba(0, 0, 0, 160);
            color: white;
            border-radius: 10px;
            padding: 10px;
            font-weight: bold;
        """)
        self.status_overlay.setFixedSize(200, 40)
        self.status_overlay.hide()  # Initially hidden
        
        video_layout.addWidget(self.video_label)
        video_layout.addWidget(self.status_overlay, 0, Qt.AlignCenter)
        main_layout.addWidget(video_container)
        
        # Control buttons
        control_layout = QHBoxLayout()
        self.start_button = QPushButton("Start")
        self.stop_button = QPushButton("Stop")
        control_layout.addWidget(self.start_button)
        control_layout.addWidget(self.stop_button)
        main_layout.addLayout(control_layout)
        
        # Connect signals
        self.start_button.clicked.connect(self.start_video)
        self.stop_button.clicked.connect(self.stop_video)
        
        # Video thread
        self.video_thread = None
        
        # Status bar
        self.statusBar().showMessage("Ready")
        
        # Frame buffer to reduce flickering
        self.current_pixmap = None

    def start_video(self):
        url = self.url_input.text().strip()
        if not url:
            self.statusBar().showMessage("Please enter a valid URL")
            return
            
        # If already running, stop first
        if self.video_thread and self.video_thread.isRunning():
            self.stop_video()
            
        try:
            # Disable start button and update UI to show waiting state
            self.start_button.setEnabled(False)
            self.start_button.setText("Connecting...")
            self.statusBar().showMessage(f"Opening: {url}")
            
            # Show the status overlay
            self.status_overlay.setText("Connecting...")
            self.status_overlay.show()
            
            # Create and start video thread
            self.video_thread = VideoThread(url)
            self.video_thread.frame_ready.connect(self.display_frame)
            self.video_thread.error.connect(self.handle_error)
            self.video_thread.start()
            
            # First frame received will enable the button again in display_frame
        except Exception as e:
            self.statusBar().showMessage(f"Failed to open: {url} {e}")
            # Re-enable start button if connection fails immediately
            self.start_button.setEnabled(True)
            self.start_button.setText("Start")
    
    def stop_video(self):
        # Stop the video thread
        if self.video_thread and self.video_thread.isRunning():
            self.video_thread.stop()
            self.video_thread = None
            
        # Update status
        self.statusBar().showMessage("Stopped")
        
        # Clear the display
        self.video_label.clear()
        self.video_label.setStyleSheet("background-color: black;")
        self.current_pixmap = None
        
        # Make sure start button is enabled and has correct text
        self.start_button.setEnabled(True)
        self.start_button.setText("Start")
        
        # Update status overlay
        self.status_overlay.setText("Stopped")
        self.status_overlay.show()
        # Hide the overlay after 2 seconds
        QTimer.singleShot(2000, self.status_overlay.hide)
    
    def display_frame(self, frame):
        h, w, ch = frame.shape
        
        # Convert to QImage and then to QPixmap
        bytes_per_line = ch * w
        q_img = QImage(frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
        
        # Scale to fit the label while maintaining aspect ratio
        pixmap = QPixmap.fromImage(q_img)
        scaled_pixmap = pixmap.scaled(self.video_label.size(), 
                                      Qt.KeepAspectRatio, 
                                      Qt.SmoothTransformation)
        
        self.current_pixmap = scaled_pixmap
        self.video_label.setPixmap(scaled_pixmap)
        
        # On first successful frame, update UI to show playing state
        if not self.start_button.isEnabled():
            self.start_button.setEnabled(True)
            self.start_button.setText("Start")
            self.statusBar().showMessage(f"Playing: {self.url_input.text().strip()}")
            
            # Hide the status overlay when we start playing
            self.status_overlay.hide()
    
    def handle_error(self, error_message):
        self.statusBar().showMessage(error_message)
        
        # If this is a terminal error, re-enable the start button
        if "Failed to" in error_message:
            self.start_button.setEnabled(True)
            self.start_button.setText("Start")
            
            # Update status overlay to show the error
            self.status_overlay.setText("Connection Failed")
            self.status_overlay.show()
        elif "reconnecting" in error_message.lower():
            # Show reconnecting message in overlay
            self.status_overlay.setText("Reconnecting...")
            self.status_overlay.show()
    
    def closeEvent(self, event):
        # Clean up when closing the window
        self.stop_video()
        event.accept()

    def resizeEvent(self, event):
        # When window is resized, rescale the current pixmap if it exists
        if self.current_pixmap:
            scaled_pixmap = self.current_pixmap.scaled(
                self.video_label.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.video_label.setPixmap(scaled_pixmap)
        super().resizeEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    player = VideoPlayer()
    player.show()
    sys.exit(app.exec())