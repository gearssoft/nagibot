#############################
## filename : server.py
## 설명 : TCP Agent 중계 Server
## 작성자 : gbox3d
## 위 주석은 수정하지 마세요.
#############################

import asyncio
import struct
import json
import time
from typing import Optional
import itertools

from protocol import ServerProtocol, ClientProtocol
from server.utils import deep_merge ,_get_by_path

class Server:
    __VERSION__ = "1.0.2-LE"  # Little-Endian 버전 표기

    def __init__(self,
                 host: Optional[str] = None,
                 port: Optional[int] = None,
                 timeout: Optional[int] = None):
        self.host = host if host is not None else "localhost"
        self.port = port if port is not None else 8282
        self.timeout = timeout if timeout is not None else 10  # 초

        self.checkcode = ServerProtocol.checkcode

        print(f"Server version {self.__VERSION__}")
        print(f"Listening on {self.host}:{self.port}, timeout={self.timeout}s, checkcode={self.checkcode}")

        self._id_counter = itertools.count(1)

        # 🔵 전역(모든 클라이언트 공유) 메타데이터 + 보호 락
        self.metadata_json: dict = {}
        self._meta_lock = asyncio.Lock()


        # 🔵 전역(모든 클라이언트 공유) 이미지 뱅크 + 보호 락
        self.image_bank: dict[int, dict] = {}   # bank_id -> {"data":bytes, "type":int, "seq":int, "ts":float, "size":int}
        self._bank_lock = asyncio.Lock()


    async def _read_exactly(self, reader: asyncio.StreamReader, n: int) -> bytes:
        return await asyncio.wait_for(reader.readexactly(n), timeout=self.timeout)

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        addr = writer.get_extra_info("peername")
        header_timeouts = 0
        print(f"[INFO] 연결: {addr}")

        write_lock = asyncio.Lock()  # per-connection write lock

        # 최신 1장 이미지 버퍼
        image_buffer: Optional[bytes] = None
        image_type: int = ServerProtocol.IMG_JPG
        image_seq: int = 0

        try:
            await asyncio.sleep(0.5)  # 클라이언트 준비 시간

            conn_id = next(self._id_counter)
            # 환영 메시지 푸시
            _welcome_obj = {
                "cmd": "welcome",
                "version": self.__VERSION__,
                "server_time": int(time.time()),
                "id": conn_id,
            }
            await ServerProtocol.send_json(writer, ServerProtocol.PUSH_JSON, _welcome_obj, write_lock)

            while True:
                # 공통 헤더 8B: checkcode(uint32 LE) + request_code(uint32 LE)
                try:
                    header = await self._read_exactly(reader, 8)
                    checkcode, request_code = struct.unpack("<II", header)
                    header_timeouts = 0
                except asyncio.TimeoutError:
                    header_timeouts += 1
                    print(f"[WARN] TIMEOUT waiting header ({header_timeouts}/{ServerProtocol.MAX_HEADER_TIMEOUTS}) from {addr}")
                    if header_timeouts >= ServerProtocol.MAX_HEADER_TIMEOUTS:
                        break
                    await ServerProtocol.send_push_alert(writer, ServerProtocol.WARN_TIMEOUT, write_lock)
                    continue

                if checkcode != self.checkcode:
                    print(f"[WARN] CHECKCODE mismatch: recv={checkcode}, expected={self.checkcode}")
                    await ServerProtocol.send_ack(writer, request_code, ServerProtocol.ERR_CHECKCODE_MISMATCH, write_lock)
                    break

                # 99: ping
                if request_code == ServerProtocol.REQ_PING:
                    print(f"[INFO] PING from {addr}")
                    await ServerProtocol.send_ack(writer, request_code, ServerProtocol.SUCCESS, write_lock)
                    continue

                # 0x10: 이미지 업로드
                elif request_code == ServerProtocol.REQ_IMG_UP:
                    try:
                        # 16B header
                        data_hdr = await self._read_exactly(reader, 16)
                        img_type = data_hdr[0]
                        bank_id  = struct.unpack("<I", data_hdr[4:8])[0]
                        img_size = struct.unpack("<I", data_hdr[8:12])[0]
                        img_seq  = struct.unpack("<I", data_hdr[12:16])[0]
                    except asyncio.TimeoutError:
                        await ServerProtocol.send_ack(writer, request_code, ServerProtocol.ERR_TIMEOUT, write_lock)
                        break
                    except Exception as e:
                        await ServerProtocol.send_ack(writer, request_code, ServerProtocol.ERR_INVALID_FORMAT, write_lock)
                        continue

                    if img_type not in (ServerProtocol.IMG_JPG, ServerProtocol.IMG_PNG, ServerProtocol.IMG_BMP):
                        await ServerProtocol.send_ack(writer, request_code, ServerProtocol.ERR_INVALID_PARAMETER, write_lock)
                        continue
                    if img_size > ServerProtocol.MAX_PAYLOAD_BYTES:
                        await ServerProtocol.send_ack(writer, request_code, ServerProtocol.ERR_INVALID_DATA, write_lock)
                        break

                    try:
                        img_data = await self._read_exactly(reader, img_size) if img_size > 0 else b""
                    except asyncio.TimeoutError:
                        await ServerProtocol.send_ack(writer, request_code, ServerProtocol.ERR_TIMEOUT, write_lock)
                        break

                    # 전역 공유 저장
                    async with self._bank_lock:
                        self.image_bank[bank_id] = {
                            "data": img_data,
                            "type": img_type,
                            "seq":  img_seq,
                            "ts":   time.time(),
                            "size": len(img_data),
                        }

                    print(f"[INFO] bank#{bank_id} <= image(type={img_type}, size={img_size}, seq={img_seq}) from {addr}")
                    await ServerProtocol.send_ack(writer, request_code, ServerProtocol.SUCCESS, write_lock)
                    continue
                # 0x11: 이미지 다운로드
                elif request_code == ServerProtocol.REQ_IMG_DOWN:
                    # 4B bank_id
                    try:
                        buf = await self._read_exactly(reader, 4)
                        bank_id = struct.unpack("<I", buf)[0]
                    except asyncio.TimeoutError:
                        await ServerProtocol.send_ack(writer, request_code, ServerProtocol.ERR_TIMEOUT, write_lock)
                        break

                    async with self._bank_lock:
                        entry = self.image_bank.get(bank_id)

                    if not entry:
                        await ServerProtocol.send_ack(writer, request_code, ServerProtocol.WARN_NO_IMAGE, write_lock)
                        continue

                    img_data = entry["data"]; img_type = entry["type"]; img_seq = entry["seq"]; img_size = entry["size"]

                    # push header
                    pkt_header = struct.pack("<II", self.checkcode, ServerProtocol.REQ_ACK)
                    # data header: < I B B I I I , 18bytes
                    data_hdr = struct.pack("<IBBIII",
                                        ServerProtocol.REQ_IMG_DOWN,
                                        ServerProtocol.SUCCESS,
                                        img_type,
                                        bank_id,
                                        img_size,
                                        img_seq)
                    async with write_lock:
                        writer.write(pkt_header)
                        writer.write(data_hdr)
                        if img_size:
                            writer.write(img_data)
                        await writer.drain()

                    print(f"[INFO] bank#{bank_id} -> image(type={img_type}, size={img_size}, seq={img_seq}) to {addr}")
                    continue

                
                # 0x01: 제어 JSON
                elif request_code == ServerProtocol.REQ_JSON:
                    try:
                        size_bytes = await self._read_exactly(reader, 4)
                        (size,) = struct.unpack("<I", size_bytes)
                    except asyncio.TimeoutError:
                        print(f"[WARN] TIMEOUT while reading size from {addr}")
                        await ServerProtocol.send_ack(writer, request_code, ServerProtocol.ERR_TIMEOUT, write_lock)
                        break

                    if size > ServerProtocol.MAX_PAYLOAD_BYTES:
                        print(f"[WARN] payload too large: {size} > {ServerProtocol.MAX_PAYLOAD_BYTES}")
                        await ServerProtocol.send_ack(writer, request_code, ServerProtocol.ERR_INVALID_DATA, write_lock)
                        break

                    try:
                        data = await self._read_exactly(reader, size) if size > 0 else b""
                    except asyncio.TimeoutError:
                        print(f"[WARN] TIMEOUT while reading body({size}B) from {addr}")
                        await ServerProtocol.send_ack(writer, request_code, ServerProtocol.ERR_TIMEOUT, write_lock)
                        break

                    try:
                        print(f"[DEBUG] JSON data from {addr}: {data[:128].decode('utf-8', errors='ignore')}...")
                        obj = json.loads(data.decode('utf-8'))
                        if not isinstance(obj, dict):
                            raise ValueError("JSON root must be object")

                        if "cmd" in obj:
                            cmd = str(obj.get("cmd", "")).lower()

                            # append: 전역 메타데이터 딥 머지
                            if cmd == "append":
                                data_field = obj.get("data", {})
                                if isinstance(data_field, dict):
                                    async with self._meta_lock:
                                        deep_merge(self.metadata_json, data_field)
                                        print(f"[INFO] Metadata updated: {self.metadata_json}")

                            # get_all: 스냅샷 반환
                            elif cmd == "get_all":
                                async with self._meta_lock:
                                    snapshot = dict(self.metadata_json)
                                response_obj = {"cmd": "all_metadata", "data": snapshot}
                                await ServerProtocol.send_json(writer, ServerProtocol.PUSH_JSON, response_obj, write_lock)
                                continue

                            # get_item: 단일 키 또는 점표기 경로 조회 + 토큰 에코
                            elif cmd == "get_item":
                                key = str(obj.get("key", ""))
                                token = obj.get("token")
                                async with self._meta_lock:
                                    if "." in key:
                                        value = _get_by_path(self.metadata_json, key)
                                    else:
                                        value = self.metadata_json.get(key, None)
                                response_obj = {
                                    "cmd": "item_metadata",
                                    "key": key,
                                    "value": value,
                                    "token": token
                                }
                                print(f"[INFO] Sending item metadata: {response_obj}")
                                await ServerProtocol.send_json(writer, ServerProtocol.PUSH_JSON, response_obj, write_lock)
                                continue
                            elif cmd == "list_banks":
                                async with self._bank_lock:
                                    banks = [
                                        {"bank_id": b_id,
                                        "img_type": e["type"],
                                        "img_size": e["size"],
                                        "img_seq":  e["seq"],
                                        "ts":       int(e["ts"])}
                                        for b_id, e in self.image_bank.items()
                                    ]
                                await ServerProtocol.send_json(writer, ServerProtocol.PUSH_JSON, {"cmd":"bank_list","banks":banks}, write_lock)
                                continue

                            elif cmd == "get_bank_info":
                                b_id = int(obj.get("bank_id", -1))
                                async with self._bank_lock:
                                    e = self.image_bank.get(b_id)
                                if e:
                                    info = {"cmd":"bank_info","bank_id":b_id,"exists":True,"img_type":e["type"],"img_size":e["size"],"img_seq":e["seq"],"ts":int(e["ts"])}
                                else:
                                    info = {"cmd":"bank_info","bank_id":b_id,"exists":False}
                                await ServerProtocol.send_json(writer, ServerProtocol.PUSH_JSON, info, write_lock)
                                continue

                            elif cmd == "clear_bank":
                                b_id = int(obj.get("bank_id", -1))
                                async with self._bank_lock:
                                    self.image_bank.pop(b_id, None)
                                await ServerProtocol.send_ack(writer, request_code, ServerProtocol.SUCCESS, write_lock)
                                continue

                            else:
                                await ServerProtocol.send_ack(writer, request_code, ServerProtocol.ERR_INVALID_PARAMETER, write_lock)
                                continue

                    except Exception as e:
                        print(f"[WARN] invalid JSON handling: {e}")
                        await ServerProtocol.send_ack(writer, request_code, ServerProtocol.ERR_INVALID_FORMAT, write_lock)
                        continue

                    # append 성공 등 기본 ACK
                    await ServerProtocol.send_ack(writer, request_code, ServerProtocol.SUCCESS, write_lock)
                    continue

                # 클라→서버 ACK 수신 (푸시 응답)
                elif request_code == ClientProtocol.__dict__.get("REQ_ACK", ServerProtocol.REQ_ACK):
                    try:
                        status_bytes = await self._read_exactly(reader, 5)
                        req_code, ack_status = struct.unpack("<IB", status_bytes)
                        print(f"[INFO] push ACK from {addr}: status={ack_status} for req_code={req_code}")
                    except asyncio.TimeoutError:
                        print(f"[WARN] TIMEOUT while reading push ACK from {addr}")
                        continue
                    except Exception as e:
                        print(f"[WARN] push ACK read error: {e}")
                        continue
                    continue

                else:
                    print(f"[WARN] unknown request: {request_code} from {addr}")
                    await ServerProtocol.send_push_status(writer, ServerProtocol.ERR_UNKNOWN_CODE, write_lock)

        except asyncio.IncompleteReadError:
            print(f"[INFO] EOF: {addr}")
        except asyncio.TimeoutError:
            print(f"[WARN] TIMEOUT: {addr}")
            try:
                await ServerProtocol.send_push_status(writer, ServerProtocol.ERR_TIMEOUT, write_lock)
            except Exception:
                print(f"[WARN] Failed to send TIMEOUT status to {addr}")
        except Exception as e:
            print(f"[ERROR] 예외: {e}")
            try:
                await ServerProtocol.send_push_status(writer, ServerProtocol.ERR_EXCEPTION, write_lock)
            except Exception:
                print(f"[WARN] Failed to send EXCEPTION status to {addr}")
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
            print(f"[INFO] 종료: {addr}")

    async def run(self):
        server = await asyncio.start_server(self.handle_client, self.host, self.port)
        print(f"[INFO] 서버 시작: {self.host}:{self.port}")
        async with server:
            await server.serve_forever()


if __name__ == "__main__":
    try:
        asyncio.run(Server().run())
    except KeyboardInterrupt:
        print("\n[INFO] 서버 종료")
