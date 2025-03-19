"""
MuJoCo 자동차 시뮬레이터 원격 제어 클라이언트
- TCP 소켓을 통한 2륜 자동차 원격 제어
- 실시간 차량 상태 수신
"""

import socket
import json
import struct
import threading
import time
import argparse
import pygame
import numpy as np
from dataclasses import dataclass

# 제어 명령 정의
@dataclass
class ControlCommand:
    forward: float = 0.0  # 전진/후진 (-1.0 ~ 1.0)
    turn: float = 0.0     # 좌/우 회전 (-1.0 ~ 1.0)
    command_id: int = 0   # 명령 ID

# 차량 상태 정의
@dataclass
class VehicleState:
    position: list = None        # 위치 [x, y, z]
    orientation: list = None     # 방향 [qw, qx, qy, qz]
    linear_velocity: list = None # 속도 [vx, vy, vz]
    angular_velocity: list = None # 각속도 [wx, wy, wz]
    left_wheel_pos: float = 0.0  # 왼쪽 바퀴 위치
    right_wheel_pos: float = 0.0 # 오른쪽 바퀴 위치
    left_wheel_vel: float = 0.0  # 왼쪽 바퀴 속도
    right_wheel_vel: float = 0.0 # 오른쪽 바퀴 속도
    timestamp: float = 0.0       # 타임스탬프
    
    def __post_init__(self):
        if self.position is None:
            self.position = [0.0, 0.0, 0.0]
        if self.orientation is None:
            self.orientation = [1.0, 0.0, 0.0, 0.0]
        if self.linear_velocity is None:
            self.linear_velocity = [0.0, 0.0, 0.0]
        if self.angular_velocity is None:
            self.angular_velocity = [0.0, 0.0, 0.0]

class CarControlClient:
    def __init__(self, host='localhost', port=5000):
        # 소켓 연결
        self.host = host
        self.port = port
        self.socket = None
        self.connected = False
        
        # 상태 및 명령
        self.state = VehicleState()
        self.command = ControlCommand()
        self.last_command_id = 0
        
        # 스레드 및 동기화
        self.receiver_thread = None
        self.running = False
        self.state_lock = threading.Lock()
        self.command_lock = threading.Lock()
        
        # GUI 관련
        self.use_gui = False
        self.screen = None
        self.clock = None
        
        print(f"클라이언트 초기화 완료. 연결 대상: {host}:{port}")
    
    def connect(self):
        """서버에 연결"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            self.socket.settimeout(5.0)  # 초기 타임아웃 설정
            self.connected = True
            
            print(f"서버 연결 성공: {self.host}:{self.port}")
            return True
        except Exception as e:
            print(f"연결 실패: {e}")
            self.socket = None
            return False
    
    def start(self, use_gui=True):
        """클라이언트 시작"""
        if not self.connected and not self.connect():
            return False
        
        self.running = True
        self.use_gui = use_gui
        
        # 수신 스레드 시작
        self.receiver_thread = threading.Thread(target=self.receiver_loop)
        self.receiver_thread.daemon = True
        self.receiver_thread.start()
        
        # GUI 초기화 (필요시)
        if use_gui:
            self.init_gui()
            self.gui_loop()
        else:
            self.command_loop()
        
        return True
    
    def init_gui(self):
        """GUI 초기화"""
        try:
            pygame.init()
            pygame.display.set_caption("차량 원격 제어")
            self.screen = pygame.display.set_mode((800, 600))
            self.clock = pygame.time.Clock()
            
            # 한글 폰트 설정
            try:
                # 시스템에 설치된 한글 지원 폰트 찾기 (Windows)
                self.font = pygame.font.SysFont("malgun gothic", 30)
            except:
                try:
                    # 시스템에 설치된 한글 지원 폰트 찾기 (macOS)
                    self.font = pygame.font.SysFont("AppleGothic", 30)
                except:
                    try:
                        # 시스템에 설치된 한글 지원 폰트 찾기 (Linux)
                        self.font = pygame.font.SysFont("NanumGothic", 30)
                    except:
                        # 마지막 대안으로 시스템 기본 폰트 사용
                        print("경고: 한글 지원 폰트를 찾을 수 없습니다. 한글이 깨질 수 있습니다.")
                        self.font = pygame.font.Font(None, 30)
            
            print("GUI 초기화 완료")
        except Exception as e:
            print(f"GUI 초기화 실패: {e}")
            self.use_gui = False
    
    def gui_loop(self):
        """GUI 기반 제어 루프"""
        try:
            while self.running:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        self.running = False
                        break
                
                # 키보드 입력 처리
                keys = pygame.key.get_pressed()
                
                with self.command_lock:
                    # 전진/후진 처리
                    if keys[pygame.K_UP]:
                        self.command.forward = min(1.0, self.command.forward + 0.05)
                    elif keys[pygame.K_DOWN]:
                        self.command.forward = max(-1.0, self.command.forward - 0.05)
                    else:
                        # 키를 누르지 않으면 서서히 감속
                        self.command.forward *= 0.95
                        if abs(self.command.forward) < 0.05:
                            self.command.forward = 0.0
                    
                    # 좌/우 회전 처리
                    if keys[pygame.K_LEFT]:
                        self.command.turn = min(1.0, self.command.turn + 0.05)
                    elif keys[pygame.K_RIGHT]:
                        self.command.turn = max(-1.0, self.command.turn - 0.05)
                    else:
                        # 키를 누르지 않으면 서서히 중앙으로
                        self.command.turn *= 0.9
                        if abs(self.command.turn) < 0.05:
                            self.command.turn = 0.0
                
                # 명령 전송
                self.send_command()
                
                # GUI 업데이트
                self.update_gui()
                
                # 프레임 레이트 제한
                self.clock.tick(30)
        
        except KeyboardInterrupt:
            print("사용자에 의해 중단됨")
        except Exception as e:
            print(f"GUI 루프 오류: {e}")
        finally:
            self.stop()
    
    def update_gui(self):
        """GUI 화면 업데이트"""
        if not self.screen:
            return
        
        # 화면 지우기
        self.screen.fill((240, 240, 240))
        
        # 차량 상태 표시
        with self.state_lock:
            state = self.state
        
        # 이전에 초기화한 폰트 사용
        font = self.font
        
        # 속도 계산 (m/s)
        speed = np.linalg.norm(state.linear_velocity)
        speed_text = f"속도: {speed:.2f} m/s"
        speed_surf = font.render(speed_text, True, (0, 0, 0))
        self.screen.blit(speed_surf, (50, 50))
        
        # 위치 표시
        pos_text = f"위치: X={state.position[0]:.2f}, Y={state.position[1]:.2f}, Z={state.position[2]:.2f}"
        pos_surf = font.render(pos_text, True, (0, 0, 0))
        self.screen.blit(pos_surf, (50, 100))
        
        # 명령 표시
        with self.command_lock:
            cmd = self.command
            
        forward_text = f"전진/후진: {cmd.forward:.2f}"
        forward_surf = font.render(forward_text, True, (0, 0, 0))
        self.screen.blit(forward_surf, (50, 150))
        
        turn_text = f"좌/우 회전: {cmd.turn:.2f}"
        turn_surf = font.render(turn_text, True, (0, 0, 0))
        self.screen.blit(turn_surf, (50, 200))
        
        # 바퀴 상태 표시
        wheel_text = f"바퀴 위치: 왼쪽={state.left_wheel_pos:.2f}, 오른쪽={state.right_wheel_pos:.2f}"
        wheel_surf = font.render(wheel_text, True, (0, 0, 0))
        self.screen.blit(wheel_surf, (50, 250))
        
        wheel_vel_text = f"바퀴 속도: 왼쪽={state.left_wheel_vel:.2f}, 오른쪽={state.right_wheel_vel:.2f}"
        wheel_vel_surf = font.render(wheel_vel_text, True, (0, 0, 0))
        self.screen.blit(wheel_vel_surf, (50, 300))
        
        # 조작 설명
        help_text = [
            "조작 방법:",
            "↑/↓: 전진/후진",
            "←/→: 좌/우 회전"
        ]
        
        for i, text in enumerate(help_text):
            help_surf = font.render(text, True, (0, 0, 0))
            self.screen.blit(help_surf, (500, 50 + i * 30))
        
        # 차량 상태 시각화 (간단한 탑뷰)
        self.draw_car_topview(400, 400, 100)
        
        pygame.display.flip()
    
    def draw_car_topview(self, x, y, size):
        """차량 탑뷰 시각화"""
        with self.state_lock:
            pos = self.state.position
            quat = self.state.orientation
        
        # 쿼터니언에서 요(yaw) 각도 계산
        yaw = 2 * np.arctan2(quat[3], quat[0])
        
        # 차체 크기
        car_length = size * 0.6
        car_width = size * 0.3
        
        # 차체 중심점
        car_center = (x, y)
        
        # 차체 방향 벡터
        dir_x, dir_y = np.cos(yaw), np.sin(yaw)
        
        # 차체 네 귀퉁이 계산
        car_points = [
            (x + dir_x * car_length/2 - dir_y * car_width/2, 
             y + dir_y * car_length/2 + dir_x * car_width/2),
            (x + dir_x * car_length/2 + dir_y * car_width/2, 
             y + dir_y * car_length/2 - dir_x * car_width/2),
            (x - dir_x * car_length/2 + dir_y * car_width/2, 
             y - dir_y * car_length/2 - dir_x * car_width/2),
            (x - dir_x * car_length/2 - dir_y * car_width/2, 
             y - dir_y * car_length/2 + dir_x * car_width/2)
        ]
        
        # 차체 그리기
        pygame.draw.polygon(self.screen, (200, 50, 50), car_points)
        
        # 진행 방향 표시
        pygame.draw.line(self.screen, (0, 0, 0), car_center, 
                          (x + dir_x * car_length/2, y + dir_y * car_length/2), 2)
        
        # 바퀴 위치 계산
        wheel_radius = size * 0.05
        wheel_positions = [
            # 왼쪽 바퀴
            (x - dir_x * car_length/3 - dir_y * car_width/2, 
             y - dir_y * car_length/3 + dir_x * car_width/2),
            # 오른쪽 바퀴
            (x - dir_x * car_length/3 + dir_y * car_width/2, 
             y - dir_y * car_length/3 - dir_x * car_width/2),
        ]
        
        # 바퀴 그리기
        for i, (wx, wy) in enumerate(wheel_positions):
            # 바퀴 그리기
            pygame.draw.circle(self.screen, (50, 50, 50), (int(wx), int(wy)), int(wheel_radius))
            
            with self.state_lock:
                if i == 0:  # 왼쪽 바퀴
                    angle = self.state.left_wheel_pos
                else:  # 오른쪽 바퀴
                    angle = self.state.right_wheel_pos
            
            # 방향 표시 (바퀴 회전 각도)
            wx2 = wx + np.cos(yaw + angle) * wheel_radius
            wy2 = wy + np.sin(yaw + angle) * wheel_radius
            pygame.draw.line(self.screen, (255, 255, 255), (wx, wy), (wx2, wy2), 1)
    
    def command_loop(self):
        """콘솔 기반 명령 루프"""
        try:
            print("콘솔 모드 시작. 'q'를 입력하여 종료")
            print("명령 형식: forward turn")
            print("예시: 0.5 0.2 (forward=0.5, turn=0.2)")
            
            while self.running:
                cmd_str = input("> ")
                if cmd_str.lower() == 'q':
                    self.running = False
                    break
                
                try:
                    parts = cmd_str.split()
                    if len(parts) >= 2:
                        with self.command_lock:
                            self.command.forward = float(parts[0])
                            self.command.turn = float(parts[1])
                        
                        # 명령 전송
                        self.send_command()
                        
                        # 상태 출력
                        with self.state_lock:
                            print(f"위치: {self.state.position}")
                            print(f"속도: {self.state.linear_velocity}")
                            print(f"바퀴 위치: 왼쪽={self.state.left_wheel_pos:.2f}, 오른쪽={self.state.right_wheel_pos:.2f}")
                    else:
                        print("형식 오류. 필요한 인자: forward turn")
                except ValueError:
                    print("숫자 변환 오류. 유효한 숫자를 입력하세요.")
                
                time.sleep(0.1)
        
        except KeyboardInterrupt:
            print("사용자에 의해 중단됨")
        except Exception as e:
            print(f"명령 루프 오류: {e}")
        finally:
            self.stop()
    
    def receiver_loop(self):
        """상태 수신 루프"""
        try:
            self.socket.settimeout(0.5)  # 소켓 타임아웃 설정
            
            while self.running and self.socket:
                try:
                    # 헤더 수신 (메시지 길이)
                    header = self.socket.recv(4)
                    if not header:
                        print("서버 연결 종료")
                        break
                    
                    msg_size = struct.unpack('!I', header)[0]
                    if msg_size > 8192:  # 최대 메시지 크기 제한
                        print(f"잘못된 메시지 크기: {msg_size}")
                        continue
                    
                    # 메시지 수신
                    data = self.socket.recv(msg_size)
                    if len(data) != msg_size:
                        print(f"불완전한 메시지 수신: {len(data)}/{msg_size}")
                        continue
                    
                    # 메시지 디코딩 및 처리
                    msg = json.loads(data.decode('utf-8'))
                    self.process_message(msg)
                    
                except socket.timeout:
                    # 타임아웃은 정상적인 처리 과정
                    continue
                except json.JSONDecodeError:
                    print(f"JSON 파싱 오류: {data}")
                    continue
                
        except Exception as e:
            print(f"수신 루프 오류: {e}")
        finally:
            if self.running:
                print("서버 연결이 끊어졌습니다.")
                self.running = False
    
    def process_message(self, msg):
        """수신된 메시지 처리"""
        # 상태 메시지인 경우
        if 'position' in msg and 'orientation' in msg:
            with self.state_lock:
                self.state.position = msg['position']
                self.state.orientation = msg['orientation']
                self.state.linear_velocity = msg['linear_velocity']
                self.state.angular_velocity = msg['angular_velocity']
                self.state.left_wheel_pos = msg.get('left_wheel_pos', 0.0)
                self.state.right_wheel_pos = msg.get('right_wheel_pos', 0.0)
                self.state.left_wheel_vel = msg.get('left_wheel_vel', 0.0)
                self.state.right_wheel_vel = msg.get('right_wheel_vel', 0.0)
                self.state.timestamp = msg['timestamp']
        
        # 응답 메시지인 경우
        elif 'status' in msg:
            if msg['status'] != 'ok':
                print(f"명령 처리 오류: {msg.get('message', '알 수 없는 오류')}")
            elif 'command_id' in msg:
                # 필요한 경우 명령 ID 처리
                pass
    
    def send_command(self):
        """제어 명령 전송"""
        if not self.socket or not self.connected:
            return False
        
        try:
            with self.command_lock:
                # 명령 ID 증가
                self.last_command_id += 1
                self.command.command_id = self.last_command_id
                
                # 명령 직렬화
                cmd_dict = {
                    'forward': round(self.command.forward, 3),
                    'turn': round(self.command.turn, 3),
                    'command_id': self.command.command_id
                }
            
            # JSON 변환 및 전송
            cmd_json = json.dumps(cmd_dict).encode('utf-8')
            header = struct.pack('!I', len(cmd_json))
            
            self.socket.sendall(header + cmd_json)
            return True
            
        except Exception as e:
            print(f"명령 전송 오류: {e}")
            self.connected = False
            return False
    
    def stop(self):
        """클라이언트 종료"""
        self.running = False
        
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            self.socket = None
        
        if self.use_gui and pygame.get_init():
            pygame.quit()
        
        print("클라이언트가 안전하게 종료되었습니다.")

# 메인 실행 부분
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='차량 시뮬레이터 원격 제어 클라이언트')
    parser.add_argument('--host', type=str, default='localhost', help='서버 호스트')
    parser.add_argument('--port', type=int, default=5000, help='서버 포트')
    parser.add_argument('--no-gui', action='store_true', help='GUI 비활성화')
    args = parser.parse_args()
    
    client = CarControlClient(host=args.host, port=args.port)
    client.start(use_gui=not args.no_gui)