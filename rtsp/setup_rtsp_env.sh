#!/usr/bin/env bash
# Ubuntu 22.04 (Jammy)에서 GStreamer RTSP + PyGObject(GI) 환경을
# "삽질 없이" 한 번에 세팅하고 미니 서버로 검증하는 스크립트.
# - 전역(Apt)으로 GI/타입라이브 설치
# - Python 3.10 venv를 system-site-packages로 구성
# - gi/Gst/GstRtspServer import 검증
# - 샘플 server.py, test용 플레이 명령 안내

set -euo pipefail

# -------- Config --------
APP_DIR="${APP_DIR:-$PWD}"           # 현재 디렉토리에 세팅 (원하면 환경변수로 바꿔주세요)
VENV_DIR="${VENV_DIR:-$APP_DIR/.venv}"
PY310_BIN="${PY310_BIN:-/usr/bin/python3.10}"
PORT="${PORT:-8554}"
MOUNT="${MOUNT:-/test}"
SAMPLE_MP4="${SAMPLE_MP4:-test.mp4}" # 이미 있으면 그대로 사용
SERVER_PY="${SERVER_PY:-server.py}"
# ------------------------

bold() { echo -e "\033[1m$*\033[0m"; }
green() { echo -e "\033[32m$*\033[0m"; }
yellow() { echo -e "\033[33m$*\033[0m"; }
red() { echo -e "\033[31m$*\033[0m"; }

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || { red "필요한 명령어가 없습니다: $1"; exit 1; }
}

bold "[1/7] Ubuntu 버전 확인"
. /etc/os-release
echo "ID=$ID VERSION_CODENAME=$VERSION_CODENAME VERSION_ID=$VERSION_ID"
if [[ "${VERSION_ID}" != "22.04" ]]; then
  yellow "이 스크립트는 Jammy(22.04) 기준입니다. 계속 진행합니다만, 환경이 다르면 패키지명이 다를 수 있습니다."
fi

bold "[2/7] APT 패키지 설치 (GI + GStreamer + 플러그인 일괄)"
sudo apt update
sudo apt install -y \
  python3-gi python3-gi-cairo \
  gir1.2-gstreamer-1.0 \
  gir1.2-gst-rtsp-server-1.0 libgstrtspserver-1.0-0 \
  gstreamer1.0-tools \
  gstreamer1.0-plugins-base gstreamer1.0-plugins-good \
  gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly

bold "[3/7] 기본 도구 확인"
need_cmd "${PY310_BIN}"
need_cmd gst-inspect-1.0
need_cmd ffprobe || yellow "ffprobe 없음(선택). 필요 시: sudo apt install -y ffmpeg"

bold "[4/7] Python 3.10 venv 생성 (system-site-packages)"
# 기존 venv 삭제 여부는 사용자 선택. 여기선 안전하게 덮어씁니다.
if [[ -d "${VENV_DIR}" ]]; then
  yellow "기존 venv 폴더가 있어 삭제합니다: ${VENV_DIR}"
  rm -rf "${VENV_DIR}"
fi

# uv가 있다면 uv로, 없으면 표준 venv 사용
if command -v uv >/dev/null 2>&1; then
  green "uv 발견: uv venv 사용"
  uv venv --python "${PY310_BIN}" --system-site-packages "${VENV_DIR}"
else
  yellow "uv 미발견: 표준 venv 사용"
  "${PY310_BIN}" -m venv --system-site-packages "${VENV_DIR}"
fi

# shellcheck disable=SC1090
source "${VENV_DIR}/bin/activate"

bold "[5/7] GI / GStreamer 바인딩 검증"
python - <<'PY'
import sys
import gi
gi.require_version('Gst', '1.0')
gi.require_version('GstRtspServer', '1.0')
from gi.repository import Gst, GstRtspServer
print("Gst OK:", Gst.version())
print("GstRtspServer OK")
PY

bold "[6/7] 샘플 RTSP 서버 스크립트 배치"
cd "${APP_DIR}"

if [[ ! -f "${SERVER_PY}" ]]; then
cat > "${SERVER_PY}" <<'PY'
#!/usr/bin/env python3
import gi
import argparse
import os
import sys

gi.require_version('Gst', '1.0')
gi.require_version('GstRtspServer', '1.0')
from gi.repository import Gst, GstRtspServer, GLib

Gst.init(None)

class FileRtspMediaFactory(GstRtspServer.RTSPMediaFactory):
    def __init__(self, mp4_path):
        super().__init__()
        launch = (
            f'( filesrc location="{mp4_path}" ! qtdemux name=demux '
            'demux.video_0 ! queue ! rtph264pay name=pay0 pt=96 '
            'demux.audio_0 ! queue ! rtpmp4apay name=pay1 pt=97 )'
        )
        self.set_launch(launch)
        self.set_shared(True)

def parse_args():
    p = argparse.ArgumentParser(description="GStreamer로 MP4 파일 RTSP 서비스 (복수 스트림 지원)")
    p.add_argument(
        '-s','--stream', action='append', required=True, metavar='FILE:MP',
        help="스트림 등록 (예: test.mp4:/test). 반복 사용 가능"
    )
    p.add_argument(
        '-p','--port', type=int, default=8554, help="리스닝 포트 (기본: 8554)"
    )
    return p.parse_args()

def main():
    args = parse_args()

    server = GstRtspServer.RTSPServer()
    server.props.service = str(args.port)
    mounts = server.get_mount_points()

    for item in args.stream:
        try:
            file_path, mount = item.split(':', 1)
        except ValueError:
            print(f"Error: 잘못된 형식: {item}", file=sys.stderr)
            sys.exit(1)

        if not os.path.isfile(file_path):
            print(f"Error: 파일을 찾을 수 없습니다: {file_path}", file=sys.stderr)
            sys.exit(1)

        if not mount.startswith('/'):
            mount = '/' + mount

        mounts.add_factory(mount, FileRtspMediaFactory(file_path))
        print(f'등록 완료 → rtsp://127.0.0.1:{args.port}{mount} (파일: {file_path})')

    server.attach(None)
    loop = GLib.MainLoop()  # 최신 방식
    loop.run()

if __name__ == '__main__':
    main()
PY
chmod +x "${SERVER_PY}"
else
  yellow "${SERVER_PY}가 이미 존재하여 덮어쓰지 않았습니다."
fi

# 샘플 파일 유무만 체크(파일 자체는 사용자가 준비)
if [[ ! -f "${SAMPLE_MP4}" ]]; then
  yellow "샘플 MP4(${SAMPLE_MP4}) 파일이 없습니다. 준비하신 후 아래 실행 예를 참고하세요."
fi

bold "[7/7] 실행/검증 방법 안내"
cat <<EOF

$(green "✅ 세팅 완료!")

가상환경 활성화:
  source "${VENV_DIR}/bin/activate"

RTSP 서버 실행 예:
  python "${SERVER_PY}" -s ${SAMPLE_MP4}:${MOUNT} -p ${PORT}

클라이언트 테스트(FFmpeg/ffplay):
  ffplay -rtsp_transport tcp rtsp://127.0.0.1:${PORT}${MOUNT}

문제 발생 시 빠른 점검:
  python - <<'PY'
import gi
gi.require_version('Gst','1.0'); from gi.repository import Gst
gi.require_version('GstRtspServer','1.0'); from gi.repository import GstRtspServer
print("Gst OK:", Gst.version()); print("GstRtspServer OK")
PY

* 만약 venv에서 import gi가 계속 실패하면(드묾), 임시 우회:
  export PYTHONPATH=/usr/lib/python3/dist-packages:\$PYTHONPATH

EOF

green "Done."
