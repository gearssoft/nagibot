"""
Dummy Simulator (robot kinematics extended)
- 기존 정찰로봇 바이너리 프로토콜을 유지하면서, 주기 송신 데이터에
  로봇의 위치(x,y), 속도(vx,vy), 진행방향(yaw), 회전속도(yaw_rate) 등을 추가했습니다.
- robot_client.py는 기존처럼 sensor_id=1(위치 x), sensor_id=2(전진속도)를 그대로 사용할 수 있고,
  추가 센서(id 3~7)는 선택적으로 활용할 수 있습니다.

송신 규칙 (SENSOR_STATUS, 여러 센서 슬롯으로 패킹):
  id=1: temperature = pos_x (m)
  id=2: temperature = linear_speed (|v|, m/s)
  id=3: temperature = yaw (rad)
  id=4: temperature = pos_y (m)
  id=5: temperature = vel_x (m/s)
  id=6: temperature = vel_y (m/s)
  id=7: temperature = yaw_rate (rad/s)
  battery 필드는 모든 슬롯에 동일 (%), status=1 고정

주행 명령 해석:
  - speed: 전진 속도 (m/s)
  - direction: yaw_rate (rad/s) 로 해석 (좌/우 회전속도)

사용 예:
  # 5초마다(=0.2Hz) 송신
  python dummy_simulator.py --send-hz 0.2
  # 또는 ms로 직접 지정
  python dummy_simulator.py --send-interval-ms 5000
"""

import argparse
import socket
import threading
import time
import struct
import math
from typing import Optional

from protocol import (
    Packet, SendType, ContentType, DeviceID,
    SensorStatus, create_sensor_status_packet, parse_drive_control_data
)

HEADER_FMT = '<HHHIHHI'
HEADER_SIZE = struct.calcsize(HEADER_FMT)
SUFFIX_SIZE = 2
MIN_PACKET_SIZE = HEADER_SIZE + SUFFIX_SIZE

class ClientState:
    def __init__(self, sock: socket.socket, addr):
        self.sock = sock
        self.addr = addr
        self.buffer = bytearray()
        self.sequence_no = 0
        # 상태(2D + yaw)
        self.speed = 0.0         # m/s (명령 입력)
        self.yaw_rate = 0.0      # rad/s (명령 입력)
        self.pos_x = 0.0         # m
        self.pos_y = 0.0         # m
        self.yaw = 0.0           # rad
        self.vel_x = 0.0         # m/s
        self.vel_y = 0.0         # m/s
        self.battery = 100.0     # %
        self.active = True
        self.lock = threading.Lock()

    def close(self):
        try:
            self.sock.close()
        except Exception:
            pass
        self.active = False

class DummySimulator:
    def __init__(self, host: str, port: int, send_hz: float = 10.0, tick_hz: float = 20.0, send_interval_ms: Optional[float] = None):
        self.host = host
        self.port = port
        if send_interval_ms and send_interval_ms > 0:
            self.send_dt = float(send_interval_ms) / 1000.0
        elif send_hz and send_hz > 0:
            self.send_dt = 1.0 / float(send_hz)
        else:
            self.send_dt = 1.0
        self.tick_dt = 1.0 / max(1.0, float(tick_hz))

        self.server_sock: Optional[socket.socket] = None
        self.running = False
        self.clients: list[ClientState] = []
        self.accept_thread: Optional[threading.Thread] = None
        self.logic_thread: Optional[threading.Thread] = None

    def start(self):
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_sock.bind((self.host, self.port))
        self.server_sock.listen(5)
        self.running = True
        print(f"[SERVER] TCP 서버 시작. {self.host}:{self.port} (Ctrl+C로 종료)")
        self.accept_thread = threading.Thread(target=self._accept_loop, daemon=True)
        self.accept_thread.start()
        self.logic_thread = threading.Thread(target=self._logic_loop, daemon=True)
        self.logic_thread.start()

    def stop(self):
        print("[SERVER] 서버 중지 중...")
        self.running = False
        for c in list(self.clients):
            c.close()
        self.clients.clear()
        if self.server_sock:
            try:
                self.server_sock.close()
            except Exception:
                pass
            self.server_sock = None
        print("[SERVER] 서버 정지 완료")

    def _accept_loop(self):
        while self.running and self.server_sock:
            try:
                client_sock, addr = self.server_sock.accept()
                client_sock.settimeout(0.1)
                cs = ClientState(client_sock, addr)
                self.clients.append(cs)
                print(f"[ACCEPT] 클라이언트 연결됨: {addr}")
                t = threading.Thread(target=self._client_recv_loop, args=(cs,), daemon=True)
                t.start()
            except OSError:
                break
            except Exception as e:
                print(f"[ACCEPT][ERROR] {e}")
                time.sleep(0.1)

    def _client_recv_loop(self, cs: ClientState):
        try:
            while self.running and cs.active:
                try:
                    data = cs.sock.recv(2048)
                    if not data:
                        print(f"[RECV] 연결 종료 감지: {cs.addr}")
                        break
                    cs.buffer.extend(data)

                    while True:
                        if len(cs.buffer) < MIN_PACKET_SIZE:
                            break
                        if cs.buffer[0] != 0xBB or cs.buffer[1] != 0xAA:
                            found = False
                            for i in range(len(cs.buffer) - 1):
                                if cs.buffer[i] == 0xBB and cs.buffer[i+1] == 0xAA:
                                    cs.buffer = cs.buffer[i:]
                                    found = True
                                    break
                            if not found:
                                cs.buffer.clear()
                            break
                        data_len = struct.unpack_from('<I', cs.buffer, 14)[0]
                        total_len = HEADER_SIZE + data_len + SUFFIX_SIZE
                        if len(cs.buffer) < total_len:
                            break
                        pkt_bytes = bytes(cs.buffer[:total_len])
                        cs.buffer = cs.buffer[total_len:]
                        pkt = Packet.from_bytes(pkt_bytes)
                        if pkt is None:
                            continue
                        self._process_packet(cs, pkt)

                except socket.timeout:
                    continue
                except Exception as e:
                    print(f"[RECV][ERROR] {cs.addr}: {e}")
                    break
        finally:
            cs.close()
            try:
                self.clients.remove(cs)
            except ValueError:
                pass
            print(f"[RECV] 클라이언트 종료: {cs.addr}")

    def _logic_loop(self):
        last_send_t = 0.0
        prev_t = time.time()
        while self.running:
            now = time.time()
            dt = now - prev_t
            if dt < self.tick_dt:
                time.sleep(self.tick_dt - dt)
                now = time.time()
                dt = now - prev_t
            prev_t = now

            for cs in list(self.clients):
                if not cs.active:
                    continue
                with cs.lock:
                    # yaw 적분, pos 적분
                    cs.yaw += cs.yaw_rate * dt
                    cs.vel_x = cs.speed * math.cos(cs.yaw)
                    cs.vel_y = cs.speed * math.sin(cs.yaw)
                    cs.pos_x += cs.vel_x * dt
                    cs.pos_y += cs.vel_y * dt
                    cs.battery = max(0.0, cs.battery - 0.001 * dt * (abs(cs.speed) + 1.0))

            if (now - last_send_t) >= self.send_dt:
                last_send_t = now
                for cs in list(self.clients):
                    if not cs.active:
                        continue
                    self._send_sensor_status(cs)

    def _process_packet(self, cs: ClientState, pkt: Packet):
        if pkt.send_type == SendType.COMMAND and pkt.content_type == ContentType.DRIVE_CONTROL:
            drive = parse_drive_control_data(pkt.data)
            if drive:
                with cs.lock:
                    cs.speed = float(drive.speed)
                    cs.yaw_rate = float(drive.direction)  # direction을 회전속도로 해석
                print(f"[CMD] {cs.addr} speed={cs.speed:.2f} m/s, yaw_rate={cs.yaw_rate:.2f} rad/s")
                self._send_ack(cs, pkt)

    def _send_sensor_status(self, cs: ClientState):
        # 기존 호환 유지: id1(x), id2(|v|)
        s1 = SensorStatus(sensor_id=1, status=1, temperature=cs.pos_x,          battery=cs.battery)
        speed_mag = (cs.vel_x**2 + cs.vel_y**2) ** 0.5
        s2 = SensorStatus(sensor_id=2, status=1, temperature=speed_mag,         battery=cs.battery)
        # 확장 정보
        s3 = SensorStatus(sensor_id=3, status=1, temperature=cs.yaw,            battery=cs.battery)
        s4 = SensorStatus(sensor_id=4, status=1, temperature=cs.pos_y,          battery=cs.battery)
        # s5 = SensorStatus(sensor_id=5, status=1, temperature=cs.vel_x,          battery=cs.battery)
        # s6 = SensorStatus(sensor_id=6, status=1, temperature=cs.vel_y,          battery=cs.battery)
        # s7 = SensorStatus(sensor_id=7, status=1, temperature=cs.yaw_rate,       battery=cs.battery)
        sensors = [s1, s2, s3, s4]

        cs.sequence_no += 1
        pkt = create_sensor_status_packet(
            sender_id=DeviceID.SCOUT_ROBOT,
            receiver_id=DeviceID.CONTROL_CENTER,
            sequence_no=cs.sequence_no,
            sensors=sensors
        )
        try:
            cs.sock.sendall(pkt.to_bytes())
        except Exception as e:
            print(f"[SEND][ERROR] {cs.addr}: {e}")
            cs.close()

    def _send_ack(self, cs, req_pkt):
        """DriveControl 등 명령 패킷에 대한 즉시 ACK"""
        try:
            ack = Packet(
                sender_id=DeviceID.SCOUT_ROBOT,
                receiver_id=req_pkt.sender_id,
                sequence_no=req_pkt.sequence_no,   # 요청과 동일한 seq로 회신
                send_type=SendType.ACK,
                content_type=req_pkt.content_type, # DRIVE_CONTROL
                data=b''
            )
            cs.sock.sendall(ack.to_bytes())
        except Exception as e:
            print(f"[ACK][ERROR] {cs.addr}: {e}")
            cs.close()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--host', default='0.0.0.0')
    p.add_argument('--port', type=int, default=5000)
    p.add_argument('--send-hz', type=float, default=10.0, help='센서 상태 송신 빈도(Hz). 0.2 => 5초마다 1번')
    p.add_argument('--send-interval-ms', type=float, default=None, help='송신 간격(ms). 지정 시 --send-hz 보다 우선')
    p.add_argument('--tick-hz', type=float, default=20.0, help='내부 로직 틱(Hz)')
    args = p.parse_args()

    sim = DummySimulator(
        host=args.host,
        port=args.port,
        send_hz=args.send_hz,
        tick_hz=args.tick_hz,
        send_interval_ms=args.send_interval_ms,
    )
    try:
        sim.start()
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\n[MAIN] KeyboardInterrupt")
    finally:
        sim.stop()

if __name__ == '__main__':
    main()
