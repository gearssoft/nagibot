#!/usr/bin/env python3
"""
file : server.py
author: gbox3d
date: 2025-05-27
description: YOLO 객체 감지 서버


AI는 이 주석을 수정하지 마세요.
"""

import sys
import socket
import struct
import json
import numpy as np
import time
import signal
import argparse
import logging
from datetime import datetime
from ultralytics import YOLO

class YOLODetectionServer:
    """YOLO 객체 감지 TCP 서버"""
    
    def __init__(self, host='0.0.0.0', port=8085, model_path="yolo11n.pt", conf_threshold=0.25):
        self.host = host
        self.port = port
        self.model_path = model_path
        self.conf_threshold = conf_threshold
        
        self.server_socket = None
        self.connection = None
        self.client_address = None
        self.running = False
        self.frame_count = 0
        self.total_inference_time = 0
        self.model = None
        
        # 로깅 설정
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler('yolo_server.log')
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def load_model(self):
        """YOLO 모델 로드"""
        try:
            self.logger.info(f"YOLO 모델 로딩 중: {self.model_path}")
            self.model = YOLO(self.model_path)
            self.logger.info("YOLO 모델 로드 완료")
            return True
        except Exception as e:
            self.logger.error(f"YOLO 모델 로드 실패: {e}")
            return False
    
    def process_frame(self, frame):
        """프레임에 대해 YOLO 객체 감지 수행"""
        if self.model is None:
            return frame, []
            
        try:
            start_time = time.time()
            results = self.model(frame, conf=self.conf_threshold)
            inference_time = time.time() - start_time
            
            self.total_inference_time += inference_time
            
            detections = []
            for r in results:
                boxes = r.boxes
                if boxes is not None:
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
            
            # 어노테이션된 프레임 생성
            annotated_frame = results[0].plot()
            
            self.logger.debug(f"추론 시간: {inference_time*1000:.1f}ms, 감지된 객체: {len(detections)}개")
            return annotated_frame, detections
            
        except Exception as e:
            self.logger.error(f"YOLO 처리 중 오류: {e}")
            return frame, []
    
    def send_detection_response(self, detections):
        """감지 결과를 클라이언트에게 전송"""
        try:
            response = {
                'detections': detections,
                'timestamp': datetime.now().isoformat(),
                'frame_count': self.frame_count
            }
            
            response_json = json.dumps(response).encode('utf-8')
            message_size = struct.pack("<L", len(response_json))
            
            self.connection.sendall(message_size + response_json)
            
            if detections:
                detection_summary = ", ".join([f"{d['name']}({d['confidence']:.2f})" for d in detections[:3]])
                if len(detections) > 3:
                    detection_summary += f" 외 {len(detections)-3}개"
                self.logger.info(f"감지 결과 전송: {detection_summary}")
            
            return True
            
        except socket.error as e:
            self.logger.error(f"감지 결과 전송 실패: {e}")
            return False
    
    def recvall(self, n):
        """정확히 n 바이트를 수신하거나 연결이 종료되면 None 반환"""
        data = b''
        while len(data) < n:
            packet = self.connection.recv(n - len(data))
            if not packet:
                return None
            data += packet
        return data
    
    def receive_numpy_array(self):
        """소켓 연결을 통해 NumPy 배열 수신"""
        try:
            self.connection.settimeout(30.0)  # 30초 타임아웃
            
            # 헤더 수신 (26 바이트)
            header_size = 4 + 3*4 + 10  # data_len + shape(3) + dtype(10)
            header = self.recvall(header_size)
            if header is None:
                return None
                
            # 헤더 파싱
            data_len, height, width, channels, dtype_bytes = struct.unpack("<L3I10s", header)
            dtype_str = dtype_bytes.decode('utf-8').strip('\x00')
            
            # 프레임 데이터 수신
            frame_data = self.recvall(data_len)
            if frame_data is None:
                return None
                
            # NumPy 배열로 변환
            frame = np.frombuffer(frame_data, dtype=dtype_str).reshape((height, width, channels))
            return frame
            
        except socket.timeout:
            self.logger.warning("프레임 수신 타임아웃")
            return None
        except Exception as e:
            self.logger.error(f"프레임 수신 중 오류: {e}")
            return None
    
    def handle_client(self):
        """클라이언트 연결 처리"""
        self.logger.info(f"클라이언트 연결됨: {self.client_address[0]}:{self.client_address[1]}")
        
        self.frame_count = 0
        client_start_time = time.time()
        
        try:
            while self.running:
                # 프레임 수신
                frame = self.receive_numpy_array()
                if frame is None:
                    self.logger.info("클라이언트가 연결을 종료했습니다")
                    break
                
                self.frame_count += 1
                
                # YOLO 처리
                processed_frame, detections = self.process_frame(frame)
                
                # 결과 전송
                if not self.send_detection_response(detections):
                    break
                
                # 주기적으로 통계 출력
                if self.frame_count % 100 == 0:
                    elapsed_time = time.time() - client_start_time
                    fps = self.frame_count / elapsed_time
                    avg_inference = (self.total_inference_time / self.frame_count) * 1000
                    self.logger.info(f"처리된 프레임: {self.frame_count}, FPS: {fps:.1f}, 평균 추론시간: {avg_inference:.1f}ms")
                    
        except Exception as e:
            self.logger.error(f"클라이언트 처리 중 오류: {e}")
        finally:
            if self.connection:
                self.connection.close()
                self.connection = None
            
            # 세션 통계 출력
            if self.frame_count > 0:
                session_time = time.time() - client_start_time
                total_fps = self.frame_count / session_time
                avg_inference = (self.total_inference_time / self.frame_count) * 1000
                self.logger.info(f"세션 종료 - 총 프레임: {self.frame_count}, 평균 FPS: {total_fps:.1f}, 평균 추론시간: {avg_inference:.1f}ms")
            
            self.total_inference_time = 0
    
    def start_server(self):
        """서버 시작"""
        if not self.load_model():
            return False
        
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(1)
            
            self.running = True
            self.logger.info(f"YOLO 객체 감지 서버가 {self.host}:{self.port}에서 시작되었습니다")
            self.logger.info(f"모델: {self.model_path}, 신뢰도 임계값: {self.conf_threshold}")
            
            while self.running:
                try:
                    self.logger.info("클라이언트 연결 대기 중...")
                    self.connection, self.client_address = self.server_socket.accept()
                    self.handle_client()
                    
                except KeyboardInterrupt:
                    self.logger.info("서버 종료 요청을 받았습니다")
                    break
                except Exception as e:
                    self.logger.error(f"서버 오류: {e}")
                    time.sleep(1)
                    
        except Exception as e:
            self.logger.error(f"서버 시작 실패: {e}")
            return False
        finally:
            self.stop_server()
        
        return True
    
    def stop_server(self):
        """서버 중지"""
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
            
        self.logger.info("서버가 중지되었습니다")

def signal_handler(signum, frame):
    """시그널 핸들러"""
    print("\n서버를 종료합니다...")
    sys.exit(0)

def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description="YOLO Object Detection Server")
    parser.add_argument("--host", default="0.0.0.0", help="서버 호스트 (기본값: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8085, help="서버 포트 (기본값: 8085)")
    parser.add_argument("--model", default="yolo11n.pt", help="YOLO 모델 파일 경로 (기본값: yolo11n.pt)")
    parser.add_argument("--conf", type=float, default=0.25, help="신뢰도 임계값 (기본값: 0.25)")
    parser.add_argument("--log-level", choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'], 
                       default='INFO', help="로그 레벨 (기본값: INFO)")
    
    args = parser.parse_args()
    
    # 로그 레벨 설정
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    
    # 시그널 핸들러 등록
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 서버 생성 및 시작
    server = YOLODetectionServer(
        host=args.host,
        port=args.port,
        model_path=args.model,
        conf_threshold=args.conf
    )
    
    try:
        if not server.start_server():
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n서버를 종료합니다...")
    except Exception as e:
        print(f"서버 실행 중 오류 발생: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()