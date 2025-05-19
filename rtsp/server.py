#!/usr/bin/env python3
import gi  # GStreamer와 GObject 라이브러리 사용
import argparse
import os
import sys

gi.require_version('Gst', '1.0')
gi.require_version('GstRtspServer', '1.0')
from gi.repository import Gst, GstRtspServer, GObject

# GStreamer 초기화
Gst.init(None)

class FileRtspMediaFactory(GstRtspServer.RTSPMediaFactory):
    def __init__(self, mp4_path):
        super().__init__()
        launch_desc = (
            f'( filesrc location="{mp4_path}" ! qtdemux name=demux '
            'demux.video_0 ! queue ! rtph264pay name=pay0 pt=96 '
            'demux.audio_0 ! queue ! rtpmp4apay name=pay1 pt=97 )'
        )
        self.set_launch(launch_desc)
        self.set_shared(True)

class RtspServer:
    def __init__(self, mount_point, mp4_path, port):
        server = GstRtspServer.RTSPServer()
        server.props.service = str(port)
        mounts = server.get_mount_points()
        mounts.add_factory(mount_point, FileRtspMediaFactory(mp4_path))
        server.attach(None)
        print(f'RTSP 서버 시작 → rtsp://127.0.0.1:{port}{mount_point}')

def parse_args():
    p = argparse.ArgumentParser(description="GStreamer로 MP4 파일 RTSP 서비스")
    p.add_argument('-f','--file', required=True, help="스트리밍할 MP4 파일 경로")
    p.add_argument('-p','--port', type=int, default=8554, help="리스닝 포트 (기본: 8554)")
    p.add_argument('-m','--mount', default='/test', help="RTSP 마운트 포인트 (기본: /test)")
    return p.parse_args()

if __name__ == '__main__':
    args = parse_args()

    # 파일 존재 검사
    if not os.path.isfile(args.file):
        print(f"Error: 파일을 찾을 수 없습니다: {args.file}", file=sys.stderr)
        sys.exit(1)

    # 마운트 포인트에 슬래시 보장
    mount = args.mount if args.mount.startswith('/') else '/' + args.mount

    RtspServer(mount, args.file, args.port)
    GObject.MainLoop().run()
