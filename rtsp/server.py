#!/usr/bin/env python3
import gi
import argparse
import os
import sys

gi.require_version('Gst', '1.0')
gi.require_version('GstRtspServer', '1.0')
from gi.repository import Gst, GstRtspServer, GLib

# GStreamer 초기화
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
        '-s','--stream',
        action='append',
        required=True,
        metavar='FILE:MP',
        help="스트림 등록 (예: test.mp4:/test). 반복 사용 가능"
    )
    p.add_argument(
        '-p','--port',
        type=int,
        default=8554,
        help="리스닝 포트 (기본: 8554)"
    )
    return p.parse_args()

if __name__ == '__main__':
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
    loop = GLib.MainLoop()  # ✅ 최신 방식
    loop.run()
