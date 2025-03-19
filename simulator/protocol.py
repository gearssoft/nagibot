"""
정찰로봇 프로토콜 (II_001)
- 정찰로봇 CSCI와 지휘통제소 CSCI 간의 통신 인터페이스
- Little-Endian 바이너리 패킷 구현

file: protocol.py
author: gbox3d

위 주석은 수정하지 마시오
"""

import struct
import enum
from typing import List, Any, Dict, Optional, Tuple

# 상수 정의
PREFIX = 0xAABB  # 패킷 시작 마커
SUFFIX = 0xEDFF  # 패킷 종료 마커

# 열거형 정의
class SendType(enum.IntEnum):
    """송신 종류"""
    COMMAND = 1       # 명령
    RESPONSE = 2      # 응답
    NOTIFICATION = 3  # 알림
    DATA = 4          # 데이터
    ACK = 5           # 승인

class ContentType(enum.IntEnum):
    """내용 종류"""
    SENSOR_STATUS = 1     # 센서 상태 정보
    SENSOR_DATA = 2       # 센서 데이터
    CONTROL_SETTINGS = 3  # 감시장비 제어/설정
    DETECTION_RESULT = 4  # 탐지·인식 알고리즘 결과
    DRIVE_CONTROL = 5     # 주행 제어/설정

class DeviceID(enum.IntEnum):
    """장치 ID"""
    CONTROL_CENTER = 1    # 지휘통제소
    SCOUT_ROBOT = 2       # 정찰로봇
    
# 패킷 클래스
class Packet:
    """정찰로봇 통신 프로토콜 패킷"""
    
    def __init__(self, 
                 sender_id: int = 0, 
                 receiver_id: int = 0, 
                 sequence_no: int = 0,
                 send_type: int = 0, 
                 content_type: int = 0, 
                 data: bytes = b''):
        self.prefix = PREFIX
        self.sender_id = sender_id
        self.receiver_id = receiver_id
        self.sequence_no = sequence_no
        self.send_type = send_type
        self.content_type = content_type
        self.data = data
        self.data_length = len(data)
        self.suffix = SUFFIX
    
    def to_bytes(self) -> bytes:
        """패킷을 바이트 배열로 직렬화"""
        # 헤더 패킹 (Little-Endian 사용, '<' 표시)
        header = struct.pack('<HHHIHHI',
                            self.prefix,
                            self.sender_id,
                            self.receiver_id,
                            self.sequence_no,
                            self.send_type,
                            self.content_type,
                            self.data_length)
        
        # 패킷 조립
        packet = header + self.data + struct.pack('<H', self.suffix)
        
        return packet
    
    @classmethod
    def from_bytes(cls, data: bytes) -> Optional['Packet']:
        """바이트 배열에서 패킷 파싱"""
        # 최소 패킷 크기 검증 (헤더 18바이트 + 접미사 2바이트)
        if len(data) < 20:
            print("Error: 패킷 길이가 너무 짧습니다.")
            return None
        
        # 헤더 파싱
        header_format = '<HHHIHHI'
        header_size = struct.calcsize(header_format)
        
        try:
            prefix, sender_id, receiver_id, sequence_no, send_type, content_type, data_length = \
                struct.unpack(header_format, data[:header_size])
        except struct.error:
            print("Error: 헤더 파싱 실패")
            return None
        
        # 프리픽스 검증
        if prefix != PREFIX:
            print(f"Error: 잘못된 프리픽스 (0x{prefix:04X}, 예상: 0x{PREFIX:04X})")
            return None
        
        # 데이터 길이 검증
        total_expected_size = header_size + data_length + 2  # 헤더 + 데이터 + 접미사
        if len(data) < total_expected_size:
            print(f"Error: 데이터 길이 불일치 (받음: {len(data)}, 예상: {total_expected_size})")
            return None
        
        # 데이터 추출
        payload = data[header_size:header_size + data_length]
        
        # 접미사 검증
        suffix_pos = header_size + data_length
        suffix = struct.unpack('<H', data[suffix_pos:suffix_pos + 2])[0]
        if suffix != SUFFIX:
            print(f"Error: 잘못된 접미사 (0x{suffix:04X}, 예상: 0x{SUFFIX:04X})")
            return None
        
        # 패킷 객체 생성
        packet = cls(sender_id, receiver_id, sequence_no, send_type, content_type, payload)
        
        return packet
    
    def __str__(self) -> str:
        """패킷 정보 문자열 반환"""
        try:
            send_type_name = SendType(self.send_type).name
        except ValueError:
            send_type_name = f"UNKNOWN({self.send_type})"
            
        try:
            content_type_name = ContentType(self.content_type).name
        except ValueError:
            content_type_name = f"UNKNOWN({self.content_type})"
        
        return (f"Packet [Sender: {self.sender_id}, Receiver: {self.receiver_id}, "
                f"Seq: {self.sequence_no}, Type: {send_type_name}, "
                f"Content: {content_type_name}, "
                f"Data Length: {self.data_length}]")


# 데이터 구조체 예시 (센서 상태)
class SensorStatus:
    """센서 상태 정보 구조체"""
    
    def __init__(self, sensor_id: int = 0, status: int = 0, 
                 temperature: float = 0.0, battery: float = 0.0):
        self.sensor_id = sensor_id
        self.status = status
        self.temperature = temperature
        self.battery = battery
    
    def to_bytes(self) -> bytes:
        """구조체를 바이트 배열로 직렬화"""
        return struct.pack('<HHff', 
                          self.sensor_id,
                          self.status,
                          self.temperature,
                          self.battery)
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'SensorStatus':
        """바이트 배열에서 구조체 파싱"""
        sensor_id, status, temperature, battery = struct.unpack('<HHff', data)
        return cls(sensor_id, status, temperature, battery)
    
    def __str__(self) -> str:
        """구조체 정보 문자열 반환"""
        status_str = "활성" if self.status == 1 else "비활성"
        return (f"센서 ID: {self.sensor_id}, 상태: {status_str}, "
                f"온도: {self.temperature:.1f}°C, 배터리: {self.battery:.1f}%")


# 드라이브 제어 구조체 예시
class DriveControl:
    """주행 제어 명령 구조체"""
    
    def __init__(self, speed: float = 0.0, direction: float = 0.0, 
                 operation_mode: int = 0):
        self.speed = speed              # 속도 (m/s)
        self.direction = direction      # 방향 (라디안)
        self.operation_mode = operation_mode  # 운용 모드
    
    def to_bytes(self) -> bytes:
        """구조체를 바이트 배열로 직렬화"""
        return struct.pack('<ffH', 
                          self.speed,
                          self.direction,
                          self.operation_mode)
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'DriveControl':
        """바이트 배열에서 구조체 파싱"""
        speed, direction, operation_mode = struct.unpack('<ffH', data)
        return cls(speed, direction, operation_mode)
    
    def __str__(self) -> str:
        """구조체 정보 문자열 반환"""
        modes = ["수동", "자율", "반자율", "비상"]
        mode_str = modes[self.operation_mode] if self.operation_mode < len(modes) else "알 수 없음"
        
        return (f"속도: {self.speed:.2f} m/s, 방향: {self.direction:.2f} rad, "
                f"운용모드: {mode_str}")


# 여러 센서 상태를 포함하는 데이터 함수
def create_sensor_status_packet(sender_id: int, receiver_id: int, 
                               sequence_no: int, sensors: List[SensorStatus]) -> Packet:
    """센서 상태 정보 패킷 생성"""
    # 모든 센서 데이터를 직렬화
    data = b''
    for sensor in sensors:
        data += sensor.to_bytes()
    
    # 패킷 생성
    return Packet(
        sender_id=sender_id,
        receiver_id=receiver_id,
        sequence_no=sequence_no,
        send_type=SendType.DATA,
        content_type=ContentType.SENSOR_STATUS,
        data=data
    )


def parse_sensor_status_data(data: bytes) -> List[SensorStatus]:
    """센서 상태 데이터 파싱"""
    sensors = []
    sensor_size = struct.calcsize('<HHff')
    
    # 데이터를 구조체 크기 단위로 파싱
    for i in range(0, len(data), sensor_size):
        if i + sensor_size <= len(data):
            sensor_data = data[i:i + sensor_size]
            sensor = SensorStatus.from_bytes(sensor_data)
            sensors.append(sensor)
    
    return sensors


def create_drive_control_packet(sender_id: int, receiver_id: int,
                               sequence_no: int, drive_control: DriveControl) -> Packet:
    """주행 제어 명령 패킷 생성"""
    # 드라이브 제어 데이터 직렬화
    data = drive_control.to_bytes()
    
    # 패킷 생성
    return Packet(
        sender_id=sender_id,
        receiver_id=receiver_id,
        sequence_no=sequence_no,
        send_type=SendType.COMMAND,
        content_type=ContentType.DRIVE_CONTROL,
        data=data
    )


def parse_drive_control_data(data: bytes) -> Optional[DriveControl]:
    """주행 제어 데이터 파싱"""
    if len(data) < struct.calcsize('<ffH'):
        return None
    
    return DriveControl.from_bytes(data)


# 패킷 사용 예시
if __name__ == "__main__":
    # 센서 상태 데이터 예시
    sensors = [
        SensorStatus(1, 1, 36.5, 95.0),  # 센서 1: 활성, 36.5°C, 배터리 95%
        SensorStatus(2, 1, 35.8, 87.5),  # 센서 2: 활성, 35.8°C, 배터리 87.5%
        SensorStatus(3, 0, 30.0, 15.0)   # 센서 3: 비활성, 30.0°C, 배터리 15%
    ]
    
    # 센서 상태 패킷 생성
    packet = create_sensor_status_packet(
        sender_id=DeviceID.SCOUT_ROBOT,     # 정찰로봇에서
        receiver_id=DeviceID.CONTROL_CENTER, # 지휘통제소로
        sequence_no=1,
        sensors=sensors
    )
    
    # 패킷 직렬화
    packet_bytes = packet.to_bytes()
    
    print(f"생성된 패킷: {packet}")
    print(f"패킷 크기: {len(packet_bytes)} 바이트")
    print(f"패킷 내용(hex): {packet_bytes.hex()}")
    
    # 패킷 파싱
    parsed_packet = Packet.from_bytes(packet_bytes)
    if parsed_packet:
        print(f"\n파싱된 패킷: {parsed_packet}")
        
        # 데이터 타입 확인 및 파싱
        if parsed_packet.content_type == ContentType.SENSOR_STATUS:
            parsed_sensors = parse_sensor_status_data(parsed_packet.data)
            print("\n센서 상태 정보:")
            for i, sensor in enumerate(parsed_sensors, 1):
                print(f"  센서 {i}: {sensor}")
    
    # 주행 제어 명령 예시
    drive_cmd = DriveControl(1.5, 0.2, 1)  # 속도 1.5m/s, 방향 0.2rad, 자율 모드
    
    # 주행 제어 패킷 생성
    drive_packet = create_drive_control_packet(
        sender_id=DeviceID.CONTROL_CENTER,  # 지휘통제소에서
        receiver_id=DeviceID.SCOUT_ROBOT,   # 정찰로봇으로
        sequence_no=1,
        drive_control=drive_cmd
    )
    
    # 패킷 직렬화
    drive_packet_bytes = drive_packet.to_bytes()
    
    print(f"\n생성된 주행 제어 패킷: {drive_packet}")
    print(f"패킷 크기: {len(drive_packet_bytes)} 바이트")
    print(f"패킷 내용(hex): {drive_packet_bytes.hex()}")
    
    # 패킷 파싱
    parsed_drive_packet = Packet.from_bytes(drive_packet_bytes)
    if parsed_drive_packet:
        print(f"\n파싱된 패킷: {parsed_drive_packet}")
        
        # 데이터 타입 확인 및 파싱
        if parsed_drive_packet.content_type == ContentType.DRIVE_CONTROL:
            parsed_drive = parse_drive_control_data(parsed_drive_packet.data)
            print(f"\n주행 제어 명령: {parsed_drive}")