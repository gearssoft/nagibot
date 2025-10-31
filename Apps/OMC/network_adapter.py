# filename: network_adapter.py
# 역할: asyncio 기반 Client를 별도 스레드 루프에서 돌리고,
#       Qt 시그널로 연결/해제/에러/메시지 등을 UI에 전달하는 어댑터

import asyncio
import threading
from typing import Optional, Callable, Any

from PySide6.QtCore import QObject, Signal

# 외부에서 제공되는 Client를 주입받습니다.
# from client.client import Client  # UI 코드 쪽에서 import 경로에 맞게 넣으세요.

class NetworkAdapter(QObject):
    # ===== 외부로 내보내는 시그널 =====
    connected = Signal(dict)         # 서버가 보낸 초기/welcome 정보
    disconnected = Signal(str)       # 끊김 사유(문자열)
    error = Signal(str)              # 예외/에러 메시지
    message = Signal(dict)           # 필요 시 일반 메시지(payload)

    def __init__(self, client_factory: Callable[[], Any], parent=None):
        """
        client_factory: 호출 시 새 Client 인스턴스를 반환하는 함수.
                        예: lambda: Client(host="localhost", port=8282)
        """
        super().__init__(parent)
        self._client_factory = client_factory

        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._loop_thread: Optional[threading.Thread] = None
        self._client: Optional[Any] = None
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    # ========== 내부: asyncio 루프 스레드 관리 ==========
    def _ensure_loop(self):
        if self._loop is not None:
            return
        self._loop = asyncio.new_event_loop()

        def _runner():
            asyncio.set_event_loop(self._loop)
            self._loop.run_forever()

        self._loop_thread = threading.Thread(target=_runner, daemon=True)
        self._loop_thread.start()

    def _run_async(self, coro, on_done=None):
        """백그라운드 이벤트 루프에서 코루틴 실행"""
        self._ensure_loop()
        fut = asyncio.run_coroutine_threadsafe(coro, self._loop)
        if on_done:
            def _cb(f):
                try:
                    on_done(f)
                except Exception as e:
                    # on_done에서 예외가 떠도 UI 크래시는 방지
                    self.error.emit(f"[on_done] {e}")
            fut.add_done_callback(_cb)
        return fut

    # ========== 외부 API ==========
    def start(self):
        """서버 연결 시작"""
        # Client 인스턴스 준비
        self._client = self._client_factory()

        # Client 콜백을 Qt 시그널로 브릿지
        self._client.on_connection_start = self._on_connection_start
        self._client.on_connection_lost = self._on_connection_lost
        # 필요 시 self._client.on_message = self._on_message  형태로 확장 가능

        def done(fut):
            try:
                _ = fut.result()  # client.start()가 리턴하는 값(보통 None)
                self._connected = True
            except Exception as e:
                self._connected = False
                self.error.emit(f"[connect] {e}")
                # 연결 실패 시 끊김 신호도 보낼지 선택
                self.disconnected.emit(str(e))

        self._run_async(self._client.start(), on_done=done)

    def stop(self):
        """서버 연결 해제"""
        if not self._connected and not self._client:
            return

        def done(fut):
            try:
                fut.result()
            except Exception as e:
                self.error.emit(f"[disconnect] {e}")
            finally:
                self._connected = False
                self._client = None

        self._run_async(self._client.stop(), on_done=done)

    # ========== Client → Adapter 콜백 ==========
    def _on_connection_start(self, json_info: dict):
        # 백그라운드 스레드에서 호출되어도, 시그널 emit은 Qt가 안전하게 메인스레드로 큐잉함
        self.connected.emit(json_info)

    def _on_connection_lost(self, reason: str):
        self._connected = False
        self._client = None
        self.disconnected.emit(reason)

    # 필요 시 일반 메시지 브릿지
    def _on_message(self, payload: dict):
        self.message.emit(payload)

    # 앱 종료 시 안전 정리(선택)
    def shutdown(self):
        try:
            if self._client and self._connected:
                self.stop()
        finally:
            if self._loop:
                loop, self._loop = self._loop, None
                if loop.is_running():
                    loop.call_soon_threadsafe(loop.stop)
            self._loop_thread = None

    # Call TCP APIs here ==========
    
    # ping 전송 ==========
    def ping_server(self):

        if not self._connected or not self._client:
            # messagebox.showwarning("Not connected", "먼저 Connect 버튼으로 서버에 연결하세요.")
            print("[UI] Cannot ping: not connected.")
            return

        def done(fut):
            try:
                ok = fut.result()  # bool
                if ok:
                    print("[UI] Ping successful.")
                else:
                    print("[UI] Ping failed.")
            except Exception as e:
                print(f"[UI] Ping error: {e}")
                
            finally:
                # 연결 상태 유지 중이면 다시 활성화
                if self._connected:
                    pass  # 필요 시 추가 동작

        self._run_async(self._client.send_ping(), on_done=done)

    # JSON by key 요청 ==========
    def fetch_json_by_key(self, key: str, *, timeout_sec: float = 5.0):
        """서버에 key 기반 JSON 요청 → message(cmd='json_item', key=..., data=...) emit"""
        if not self._connected or not self._client:
            self.error.emit("Not connected")
            # 실패도 동일 cmd로 내려서 UI가 한 곳에서 처리 가능하게
            self.message.emit({"cmd": "json_item", "key": key, "ok": False, "data": None, "error": "not connected"})
            return

        async def _task():
            import asyncio
            coro = self._client.request_json_by_key(key)
            res = await asyncio.wait_for(coro, timeout=timeout_sec) if timeout_sec and timeout_sec > 0 else await coro
            return res  # dict | None (서버 구현에 따름)

        def done(fut):
            try:
                res = fut.result()
                self.message.emit({"cmd": "json_item", "key": key, "ok": True, "data": res})
            except Exception as e:
                self.error.emit(f"[json_by_key:{key}] {e}")
                self.message.emit({"cmd": "json_item", "key": key, "ok": False, "data": None, "error": str(e)})

        self._run_async(_task(), on_done=done)

