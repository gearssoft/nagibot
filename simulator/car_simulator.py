"""
MuJoCo 기반 자동차 시뮬레이터
- 새로운 차량 모델 (2륜 차량)
- 정찰로봇 프로토콜을 통한 원격 제어 기능

author: gbox3d

위 주석은 수정하지 마시오
"""

import numpy as np
import mujoco
import socket
import threading
import time
import argparse
import struct
import os
from dataclasses import dataclass
import pygame
from contextlib import contextmanager

# 정찰로봇 프로토콜 임포트
from protocol import (
    Packet, SendType, ContentType, DeviceID,
    DriveControl, SensorStatus,
    create_sensor_status_packet, parse_drive_control_data
)

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

# 렌더러 클래스 (Pygame 사용)
class Renderer:
    def __init__(self, model, data, width=640, height=480):
        self.model = model
        self.data = data
        self.width = width
        self.height = height
        self.screen = None
        self.clock = None
        self.is_alive = False
        self.simulator = None  # 시뮬레이터 참조 추가
        self.cam = mujoco.MjvCamera()
        self.opt = mujoco.MjvOption()
        self.viewport = mujoco.MjrRect(0, 0, width, height)
        
    def init(self):
        pygame.init()
        pygame.display.set_caption("MuJoCo Car Simulator")
        self.screen = pygame.display.set_mode((self.width, self.height), pygame.OPENGL | pygame.DOUBLEBUF)
        self.clock = pygame.time.Clock()
        
        self.ctx = mujoco.MjrContext(self.model, mujoco.mjtFontScale.mjFONTSCALE_150)
        self.scene = mujoco.MjvScene(self.model, maxgeom=1000)
        
        mujoco.mjv_defaultCamera(self.cam)
        mujoco.mjv_defaultOption(self.opt)
        
        # 카메라 위치 설정
        self.cam.lookat[0] = 0
        self.cam.lookat[1] = 0
        self.cam.lookat[2] = 0.03
        self.cam.distance = 0.5
        self.cam.elevation = -20
        self.cam.azimuth = 90
        
        # 렌더러 활성화
        self.is_alive = True
        
        print("렌더러 초기화 완료")
        
    def render(self):
        if not self.is_alive:
            return
            
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                print("창 닫기 이벤트 감지")
                self.is_alive = False
                # 전체 시뮬레이터 종료 트리거 (창 닫기 이벤트 연결)
                if hasattr(self, 'simulator') and self.simulator is not None:
                    print("시뮬레이터 종료 신호 전송")
                    self.simulator.running = False
                return  # 즉시 반환하여 더 이상 렌더링하지 않음
            
        # 장면 업데이트
        mujoco.mjv_updateScene(
            self.model, self.data, self.opt, None, self.cam, 
            mujoco.mjtCatBit.mjCAT_ALL.value, self.scene
        )
        
        # 렌더링
        mujoco.mjr_render(self.viewport, self.scene, self.ctx)
        
        pygame.display.flip()
        self.clock.tick(60)
        
    def close(self):
        # 최신 MuJoCo 버전에서는 컨텍스트 관리가 자동으로 이루어짐
        # 명시적으로 컨텍스트를 해제할 필요가 없어 mjr_freeContext는 필요하지 않음
        self.ctx = None
        if self.screen is not None:
            pygame.quit()
            self.screen = None
        self.is_alive = False

class CarSimulator:
    def __init__(self, port=5000, model_path='new_car_model.xml'):
        # MuJoCo 모델 로드
        try:
            # XML 파일에서 모델 로드
            self.model = mujoco.MjModel.from_xml_path(model_path)
            print(f"모델 파일 '{model_path}'에서 로드 완료")
        except Exception as e:
            print(f"모델 파일 '{model_path}' 로드 실패: {e}")
            exit(1)
            
        self.data = mujoco.MjData(self.model)
        
        # 뷰어 설정
        self.renderer = None
        self.render_thread = None
        self.running = False
        
        # 시퀀스 번호 관리
        self.sequence_no = 0
        
        # TCP 서버 설정
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(('0.0.0.0', port))
        self.server_socket.listen(1)
        self.client_socket = None
        self.tcp_thread = None
        
        # 시뮬레이션 설정
        self.sim_time = 0.0
        self.dt = self.model.opt.timestep
        
        # 액추에이터 ID 찾기
        self.forward_id = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_ACTUATOR, "forward")
        self.turn_id = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_ACTUATOR, "turn")
        
        # 조인트 ID 찾기
        self.left_wheel_id = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_JOINT, "left")
        self.right_wheel_id = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_JOINT, "right")
        
        print(f"시뮬레이터 초기화 완료. TCP 서버 포트: {port}")
    
    def start(self, render=True):
        """시뮬레이터 시작"""
        self.running = True
        
        # 렌더링 스레드 시작 (필요시)
        if render:
            print("렌더러 생성 중...")
            self.renderer = Renderer(self.model, self.data)
            # 렌더러에서 시뮬레이터 참조 설정 (창 닫기 이벤트를 연결하기 위해)
            self.renderer.simulator = self
            
            # 렌더링 스레드 시작
            print("렌더링 스레드 시작 중...")
            self.render_thread = threading.Thread(target=self.render_loop)
            self.render_thread.daemon = True
            self.render_thread.start()
            
            # 렌더러가 초기화될 시간을 줌
            time.sleep(0.5)
        
        # TCP 서버 스레드 시작
        self.tcp_thread = threading.Thread(target=self.tcp_server_loop)
        self.tcp_thread.daemon = True
        self.tcp_thread.start()
        
        # 메인 시뮬레이션 루프
        print("시뮬레이션 루프 시작...")
        self.simulation_loop()
    
    def simulation_loop(self):
        """메인 시뮬레이션 루프"""
        try:
            # 렌더러가 초기화될 시간을 줌
            if hasattr(self, 'renderer') and self.renderer:
                time.sleep(0.5)
                
            while self.running:
                # 렌더러가 종료되었는지 확인 (렌더러가 있고, 명시적으로 is_alive가 False인 경우에만 종료)
                if hasattr(self, 'renderer') and self.renderer and self.renderer.is_alive == False:
                    print("렌더러 종료 감지, 시뮬레이션 종료합니다.")
                    break
                
                # 시뮬레이션 단계 실행
                mujoco.mj_step(self.model, self.data)
                self.sim_time += self.dt
                
                # 상태 업데이트 및 전송
                if self.client_socket:
                    self.send_vehicle_state()
                
                # 프레임 레이트 조절 (실시간 시뮬레이션을 위해)
                time.sleep(max(0, self.dt - 0.001))

        except Exception as e:
            print(f"시뮬레이션 오류: {e}")
                
        except KeyboardInterrupt:
            print("시뮬레이션 중단됨")
        finally:
            print("시뮬레이터 종료 중... stop() 호출")
            self.stop()
    
    def render_loop(self):
        """렌더링 루프"""
        try:
            print("렌더러 초기화 시작...")
            self.renderer.init()
            print("렌더링 루프 시작...")
            
            while self.running and self.renderer.is_alive:
                self.renderer.render()
                
        except Exception as e:
            print(f"렌더링 오류: {e}")
        finally:
            print("렌더링 루프 종료")
            if self.renderer:
                self.renderer.close()
    
    def tcp_server_loop(self):
        """TCP 서버 루프"""
        print("TCP 서버 시작. 클라이언트 연결 대기 중...")
        
        try:
            while self.running:
                try:
                    # 클라이언트 연결 대기
                    self.server_socket.settimeout(1.0)
                    client_sock, client_addr = self.server_socket.accept()
                    self.client_socket = client_sock
                    print(f"클라이언트 연결됨: {client_addr}")
                    
                    # 클라이언트 통신 처리
                    self.handle_client()
                except socket.timeout:
                    continue
                except OSError as e:
                    # 소켓이 닫혔거나 유효하지 않을 때 발생하는 오류
                    if not self.running:
                        # 의도적으로 시뮬레이터가 종료된 경우
                        break
                    print(f"TCP 서버 소켓 오류: {e}")
                    if self.client_socket:
                        try:
                            self.client_socket.close()
                        except:
                            pass
                        self.client_socket = None
                except Exception as e:
                    if not self.running:
                        # 의도적으로 시뮬레이터가 종료된 경우
                        break
                    print(f"TCP 서버 오류: {e}")
                    if self.client_socket:
                        try:
                            self.client_socket.close()
                        except:
                            pass
                        self.client_socket = None
        finally:
            try:
                if self.server_socket:
                    self.server_socket.close()
            except:
                pass
    
    def handle_client(self):
        """클라이언트 통신 처리"""
        buffer = bytearray()
        
        try:
            self.client_socket.settimeout(0.1)
            
            while self.running and self.client_socket:
                try:
                    # 데이터 수신
                    data = self.client_socket.recv(1024)
                    if not data:
                        print("클라이언트 연결 종료")
                        break
                    
                    # 수신 데이터를 버퍼에 추가
                    buffer.extend(data)
                    
                    # 완전한 패킷 처리
                    while True:
                        # 최소 패킷 크기는 20바이트 (헤더 18바이트 + 접미사 2바이트)
                        if len(buffer) < 20:
                            break
                        
                        # 프리픽스 확인
                        if buffer[0] != 0xBB or buffer[1] != 0xAA:  # Little-Endian에서 0xAABB
                            # 프리픽스를 찾을 때까지 버퍼 이동
                            found = False
                            for i in range(len(buffer) - 1):
                                if buffer[i] == 0xBB and buffer[i+1] == 0xAA:
                                    buffer = buffer[i:]
                                    found = True
                                    break
                            if not found:
                                buffer.clear()
                            break
                        
                        # 데이터 길이 확인
                        data_length = struct.unpack_from('<I', buffer, 14)[0]
                        
                        # 전체 패킷 길이 계산 (헤더 18바이트 + 데이터 길이 + 접미사 2바이트)
                        total_length = 18 + data_length + 2
                        
                        # 완전한 패킷이 수신되었는지 확인
                        if len(buffer) < total_length:
                            break
                            
                        # 패킷 추출
                        packet_data = bytes(buffer[:total_length])
                        
                        # 패킷 처리
                        packet = Packet.from_bytes(packet_data)
                        if packet:
                            self.process_packet(packet)
                            
                        # 처리된 패킷 제거
                        buffer = buffer[total_length:]
                    
                except socket.timeout:
                    # 타임아웃은 정상적인 처리 과정
                    pass
                
        except Exception as e:
            print(f"클라이언트 통신 오류: {e}")
        finally:
            if self.client_socket:
                self.client_socket.close()
                self.client_socket = None
            print("클라이언트 연결 종료")
    
    def process_packet(self, packet):
        """패킷 처리"""
        print(f"패킷 수신: {packet}")
        
        # 패킷 타입에 따른 처리
        if packet.content_type == ContentType.DRIVE_CONTROL and packet.send_type == SendType.COMMAND:
            # 주행 제어 명령 처리
            drive_control = parse_drive_control_data(packet.data)
            if drive_control:
                print(f"주행 제어 명령 수신: {drive_control}")
                
                # 주행 제어 명령 적용
                speed = drive_control.speed  # 속도
                direction = drive_control.direction  # 방향
                
                # 속도와 회전을 forward/turn 값으로 변환
                # 속도를 -1.0 ~ 1.0 범위로 정규화
                forward = min(max(speed / 2.0, -1.0), 1.0)
                
                # 방향을 -1.0 ~ 1.0 범위로 정규화 (라디안에서 변환)
                # 여기서는 방향 값을 그대로 사용하지만, 실제로는 적절한 변환이 필요할 수 있음
                turn = min(max(direction / 1.0, -1.0), 1.0)
                
                # 액추에이터에 명령 적용
                self.data.ctrl[self.forward_id] = forward
                self.data.ctrl[self.turn_id] = turn
                
                # 응답 패킷 전송 (ACK)
                self.send_ack(packet.sequence_no, packet.sender_id,packet.content_type)
    
    def send_ack(self, seq_no, receiver_id,content_type):
        """ACK 패킷 전송"""
        if not self.client_socket:
            return
            
        try:
            ack_packet = Packet(
                sender_id=DeviceID.SCOUT_ROBOT,
                receiver_id=receiver_id,
                sequence_no=seq_no,
                send_type=SendType.ACK,
                content_type= content_type,
                data=b''
            )
            
            packet_bytes = ack_packet.to_bytes()
            self.client_socket.sendall(packet_bytes)
            
        except Exception as e:
            print(f"ACK 패킷 전송 오류: {e}")
    
    def send_vehicle_state(self):
        """차량 상태 전송"""
        if not self.client_socket:
            return
            
        try:
            # 시퀀스 번호 증가
            self.sequence_no += 1
            
            # 센서 상태 목록 생성
            sensors = []
            
            # 차량 ID
            car_id = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_BODY, "car")
            
            # 위치와 방향 (쿼터니언)
            pos = self.data.xpos[car_id].copy().tolist()
            quat = self.data.xquat[car_id].copy().tolist()
            
            # 선속도와 각속도
            vel = self.data.qvel[0:3].copy().tolist()
            # ang_vel = self.data.qvel[3:6].copy().tolist()
            
            # 바퀴 위치 및 속도
            # 왼쪽 바퀴의 qpos 인덱스 얻기
            left_wheel_qpos_index = self.model.jnt_qposadr[self.left_wheel_id]
            # 오른쪽 바퀴의 qpos 인덱스 얻기
            right_wheel_qpos_index = self.model.jnt_qposadr[self.right_wheel_id]

            # 왼쪽 바퀴의 qvel 인덱스 얻기
            left_wheel_qvel_index = self.model.jnt_dofadr[self.left_wheel_id]
            # 오른쪽 바퀴의 qvel 인덱스 얻기
            right_wheel_qvel_index = self.model.jnt_dofadr[self.right_wheel_id]

            left_wheel_pos = float(self.data.qpos[left_wheel_qpos_index])
            right_wheel_pos = float(self.data.qpos[right_wheel_qpos_index])
            left_wheel_vel = float(self.data.qvel[left_wheel_qvel_index])
            right_wheel_vel = float(self.data.qvel[right_wheel_qvel_index])

            
            # 위치 센서 (x, y, z 좌표를 온도로 사용)
            position_sensor = SensorStatus(
                sensor_id=1,  # 위치 센서 ID
                status=1,     # 활성 상태
                temperature=pos[0],  # X 좌표를 온도로 사용
                battery=100.0  # 배터리 100%
            )
            sensors.append(position_sensor)
            
            # 속도 센서 (속도를 온도로 사용)
            velocity_sensor = SensorStatus(
                sensor_id=2,  # 속도 센서 ID
                status=1,     # 활성 상태
                temperature=np.linalg.norm(vel),  # 속도 크기를 온도로 사용
                battery=100.0  # 배터리 100%
            )
            sensors.append(velocity_sensor)
            
            # 왼쪽 바퀴 센서
            left_wheel_sensor = SensorStatus(
                sensor_id=3,  # 왼쪽 바퀴 센서 ID
                status=1,     # 활성 상태
                temperature=left_wheel_vel,  # 바퀴 속도를 온도로 사용
                battery=95.0  # 배터리 95%
            )
            sensors.append(left_wheel_sensor)
            
            # 오른쪽 바퀴 센서
            right_wheel_sensor = SensorStatus(
                sensor_id=4,  # 오른쪽 바퀴 센서 ID
                status=1,     # 활성 상태
                temperature=right_wheel_vel,  # 바퀴 속도를 온도로 사용
                battery=95.0  # 배터리 95%
            )
            sensors.append(right_wheel_sensor)
            
            # 센서 상태 패킷 생성
            packet = create_sensor_status_packet(
                sender_id=DeviceID.SCOUT_ROBOT,
                receiver_id=DeviceID.CONTROL_CENTER,
                sequence_no=self.sequence_no,
                sensors=sensors
            )
            
            # 패킷 전송
            packet_bytes = packet.to_bytes()
            self.client_socket.sendall(packet_bytes)
            
        except Exception as e:
            print(f"상태 전송 오류: {e}")
    
    def stop(self):
        """시뮬레이터 종료"""
        if not self.running:
            # 이미 종료 중인 경우 중복 실행 방지
            return
            
        print("시뮬레이터 종료 시작...")
        self.running = False
        
        # 소켓 연결 종료
        try:
            if self.client_socket:
                self.client_socket.close()
                self.client_socket = None
        except Exception as e:
            print(f"클라이언트 소켓 종료 오류: {e}")
        
        try:
            if self.server_socket:
                self.server_socket.close()
                self.server_socket = None
        except Exception as e:
            print(f"서버 소켓 종료 오류: {e}")
        
        # 렌더러 종료
        if self.renderer:
            try:
                self.renderer.close()
            except Exception as e:
                print(f"렌더러 종료 오류: {e}")
        
        # 스레드 종료 대기
        if self.render_thread and self.render_thread.is_alive():
            try:
                self.render_thread.join(timeout=1.0)
            except Exception as e:
                print(f"렌더 스레드 종료 오류: {e}")
            
        if self.tcp_thread and self.tcp_thread.is_alive():
            try:
                self.tcp_thread.join(timeout=1.0)
            except Exception as e:
                print(f"TCP 스레드 종료 오류: {e}")
        
        print("시뮬레이터가 안전하게 종료되었습니다.")
        
        # 프로그램 종료
        if __name__ == "__main__":
            import sys
            sys.exit(0)

# 메인 실행 부분
if __name__ == "__main__":
    import sys
    
    parser = argparse.ArgumentParser(description='MuJoCo 기반 차량 시뮬레이터')
    parser.add_argument('--port', type=int, default=5000, help='TCP 서버 포트')
    parser.add_argument('--no-render', action='store_true', help='렌더링 비활성화')
    parser.add_argument('--model', type=str, default='car_model.xml', help='차량 모델 XML 파일 경로')
    args = parser.parse_args()
    
    # 모델 파일 경로 확인
    if not os.path.exists(args.model):
        print(f"오류: 모델 파일 '{args.model}'을 찾을 수 없습니다.")
        print("현재 디렉토리에 car_model.xml 파일이 있는지 확인하세요.")
        sys.exit(1)
    
    simulator = CarSimulator(port=args.port, model_path=args.model)
    simulator.start(render=not args.no_render)