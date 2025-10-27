#%% asyncio TCP client test app (ACK for REQ_PUSH + image up/down)
import asyncio
import json
import struct
from typing import Dict, Optional, Union
from pathlib import Path
import time

CHECKCODE = 20251004
REQ_PING    = 99
REQ_JSON    = 0x01
REQ_PUSH    = 0x02   # s->c push , c->s ACK
REQ_IMG_UP  = 0x10   # c->s image upload
REQ_IMG_DOWN= 0x11   # c->s request image, s->c image(or status)

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8282

# image types
IMG_JPG = 0x00
IMG_PNG = 0x01
IMG_BMP = 0x02

TYPE_FROM_EXT = {
    ".jpg": IMG_JPG, ".jpeg": IMG_JPG,
    ".png": IMG_PNG,
    ".bmp": IMG_BMP,
}
EXT_FROM_TYPE = {IMG_JPG: "jpg", IMG_PNG: "png", IMG_BMP: "bmp"}

class TestClientApp:
    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT,
                 checkcode: int = CHECKCODE, timeout: float = 15.0):
        self.host = host
        self.port = port
        self.checkcode = checkcode
        self.timeout = timeout

        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None

        # 요청별 waiters
        self.waiters: Dict[int, asyncio.Queue] = {
            REQ_PING: asyncio.Queue(),
            REQ_JSON: asyncio.Queue(),
            REQ_IMG_UP: asyncio.Queue(),
            REQ_IMG_DOWN: asyncio.Queue(),
        }

        self._recv_task: Optional[asyncio.Task] = None
        self._write_lock = asyncio.Lock()   # 동시 write 보호
        self._closed = False

    async def start(self):
        try:
            self.reader, self.writer = await asyncio.open_connection(self.host, self.port)
            print(f"[CLIENT] connected -> {self.host}:{self.port}")
            self._recv_task = asyncio.create_task(self._recv_loop())
        except Exception as e:
            print(f"[CLIENT] failed to connect: {e}")

    async def stop(self):
        if self._closed:
            return
        self._closed = True
        if self._recv_task and not self._recv_task.done():
            self._recv_task.cancel()
            try:
                await self._recv_task
            except asyncio.CancelledError:
                pass
        if self.writer:
            self.writer.close()
            try:
                await self.writer.wait_closed()
            except Exception:
                pass
        print("[CLIENT] closed")

    async def _read_exactly(self, n: int) -> bytes:
        assert self.reader is not None
        return await asyncio.wait_for(self.reader.readexactly(n), timeout=self.timeout)

    async def _sendall(self, data: bytes):
        assert self.writer is not None
        async with self._write_lock:
            self.writer.write(data)
            await self.writer.drain()

    # ---------- 기본 요청 ----------
    async def send_ping(self) -> int:
        header = struct.pack("!II", self.checkcode, REQ_PING)
        await self._sendall(header)
        status = await asyncio.wait_for(self.waiters[REQ_PING].get(), timeout=self.timeout)
        return status

    async def send_json(self, obj: dict) -> int:
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        header = struct.pack("!II", self.checkcode, REQ_JSON)
        size   = struct.pack("!I", len(body))
        await self._sendall(header + size + body)
        status = await asyncio.wait_for(self.waiters[REQ_JSON].get(), timeout=self.timeout)
        return status

    async def send_push_ack(self, status: int = 0):
        """REQ_PUSH(0x02) ACK: header + status(1B)"""
        pkt = struct.pack("!IIB", self.checkcode, REQ_PUSH, status)
        await self._sendall(pkt)

    # ---------- 이미지 업/다운 ----------
    @staticmethod
    def _infer_img_type(path: Path) -> int:
        t = TYPE_FROM_EXT.get(path.suffix.lower())
        if t is None:
            raise ValueError(f"unsupported image extension: {path.suffix}")
        return t

    async def send_image(self, path: Union[str, Path], seq: int = 0, img_type: Optional[int] = None) -> int:
        """0x10 업로드: header(8) + data_hdr(16) + body"""
        p = Path(path)
        data = p.read_bytes()
        if img_type is None:
            img_type = self._infer_img_type(p)

        if len(data) > (16 * 1024 * 1024):
            raise ValueError("image too large (>16MB)")

        header = struct.pack("!II", self.checkcode, REQ_IMG_UP)

        # data header: type(1) + reserved(7 zeros) + size(4) + seq(4)
        data_hdr = bytearray(16)
        data_hdr[0] = img_type
        struct.pack_into("!I", data_hdr, 8, len(data))
        struct.pack_into("!I", data_hdr, 12, seq)

        await self._sendall(header + data_hdr + data)
        status = await asyncio.wait_for(self.waiters[REQ_IMG_UP].get(), timeout=self.timeout)
        return status

    async def request_image(self, save_to: Optional[Union[str, Path]] = None):
        """0x11 다운로드: 서버가
           - (있음) header(8)+data_hdr(16)+body 로 응답 → 파일 저장
           - (없음) header(8)+status(1) 로 ERR_INVALID_DATA 응답
        """
        header = struct.pack("!II", self.checkcode, REQ_IMG_DOWN)
        await self._sendall(header)

        res = await asyncio.wait_for(self.waiters[REQ_IMG_DOWN].get(), timeout=self.timeout)
        if isinstance(res, int):
            # status path
            print(f"[DOWN] status={res}")
            return None

        # data path
        img_type = res["type"]
        img_seq  = res["seq"]
        img_data = res["data"]

        if save_to is None:
            ts = time.strftime("%Y%m%d_%H%M%S")
            ext = EXT_FROM_TYPE.get(img_type, "bin")
            save_to = Path(f"download_{img_seq}_{ts}.{ext}")
        else:
            save_to = Path(save_to)

        save_to.write_bytes(img_data)
        print(f"[DOWN] saved -> {save_to} (type={img_type}, seq={img_seq}, size={len(img_data)}B)")
        return str(save_to)

    # ---------- 수신 루프 ----------
    async def _recv_loop(self):
        try:
            while True:

                try:
                    header = await self._read_exactly(8)
                except asyncio.TimeoutError:
                    print("[CLIENT][WARN] recv timeout")
                    continue
                r_check, r_req = struct.unpack("!II", header)

                if r_check != self.checkcode:
                    print(f"[CLIENT][WARN] checkcode mismatch: got={r_check}, expected={self.checkcode}")
                    return

                if r_req == REQ_PUSH:
                    # s->c push: size + body(JSON)
                    size_bytes = await self._read_exactly(4)
                    (size,) = struct.unpack("!I", size_bytes)
                    body = await self._read_exactly(size) if size > 0 else b""
                    try:
                        msg = json.loads(body.decode("utf-8"))
                    except Exception:
                        msg = {"raw": body[:128].hex()}
                    print(f"[PUSH] {msg}")

                    # 즉시 ACK
                    try:
                        await self.send_push_ack(status=0)
                    except Exception as e:
                        print(f"[CLIENT][ERROR] push-ack send failed: {e}")
                    continue

                elif r_req == REQ_IMG_DOWN:
                    # 다음이 status(1B) 일 수도, data_hdr(16B) 일 수도 있음
                    # 1바이트 먼저 읽고, 이어서 15바이트를 "짧은 타임아웃"으로 시도하여 판별
                    b0 = await self._read_exactly(1)
                    try:
                        rest = await asyncio.wait_for(self.reader.readexactly(15), timeout=0.05)
                        data_hdr = b0 + rest
                        img_type = data_hdr[0]
                        img_size = struct.unpack("!I", data_hdr[8:12])[0]
                        img_seq  = struct.unpack("!I", data_hdr[12:16])[0]
                        img_data = await self._read_exactly(img_size) if img_size > 0 else b""
                        self.waiters[REQ_IMG_DOWN].put_nowait({"type": img_type, "seq": img_seq, "data": img_data})
                    except asyncio.TimeoutError:
                        # 상태바이트로 간주
                        status = b0[0]
                        self.waiters[REQ_IMG_DOWN].put_nowait(status)
                    continue

                else:
                    # status only (1B) 응답 공통 처리
                    status_bytes = await self._read_exactly(1)
                    (status,) = struct.unpack("!B", status_bytes)
                    q = self.waiters.get(r_req)
                    if q is not None:
                        q.put_nowait(status)
                    else:
                        print(f"[CLIENT][INFO] resp for req={r_req}, status={status}")
                    continue

        except asyncio.IncompleteReadError:
            print("[CLIENT][INFO] server closed connection")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"[CLIENT][ERROR] recv_loop: {e}")

# ---- REPL ----
async def ainput(prompt: str = "") -> str:
    return await asyncio.to_thread(input, prompt)

async def repl(app: TestClientApp):
    print("Commands: ping | start | stop | json {..} | up <path> [seq] | down [savepath] | help | quit")
    while True:
        cmdline = (await ainput("> ")).strip()
        if not cmdline:
            continue
        low = cmdline.lower()
        if low in ("quit","q","exit"):
            break
        if low == "help":
            print("ping | start | stop | json {..} | up <path> [seq] | down [savepath] | quit"); continue
        if low == "ping":
            print("[CMD][ping] status=", await app.send_ping()); continue
        if low == "start":
            print("[CMD][start] status=", await app.send_json({"msg":"start"})); continue
        if low == "stop":
            print("[CMD][stop] status=", await app.send_json({"msg":"stop"})); continue
        if low.startswith("json "):
            raw = cmdline.split(" ", 1)[1]
            try: obj = json.loads(raw)
            except Exception as e: print("[CMD][json] invalid:", e); continue
            print("[CMD][json] status=", await app.send_json(obj)); continue
        if low.startswith("up "):
            parts = cmdline.split()
            path = parts[1]
            seq = int(parts[2]) if len(parts) > 2 else 0
            try:
                st = await app.send_image(path, seq=seq)
                print(f"[CMD][up] status={st}")
            except Exception as e:
                print(f"[CMD][up] error: {e}")
            continue
        if low.startswith("down"):
            parts = cmdline.split(maxsplit=1)
            save_to = parts[1] if len(parts) > 1 else None
            try:
                await app.request_image(save_to)
            except Exception as e:
                print(f"[CMD][down] error: {e}")
            continue

        print(f"[REPL] unknown command: {cmdline}")

# ---- main ----
async def main(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT):
    app = TestClientApp(host, port, CHECKCODE)
    try:
        await app.start()
        await repl(app)
    finally:
        await app.stop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[CLIENT] KeyboardInterrupt")
