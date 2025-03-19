#!/usr/bin/env python
import glfw
import mujoco
import sys

def main(xml_file):
    # 1) MuJoCo 모델 로드
    try:
        model = mujoco.MjModel.from_xml_path(xml_file)
    except Exception as e:
        print(f"MuJoCo 모델 로드 오류: {e}")
        return
    
    data = mujoco.MjData(model)
    
    # 2) GLFW 초기화
    if not glfw.init():
        print("GLFW 초기화 실패")
        return
    
    # 3) 윈도우 생성
    width, height = 800, 600
    window = glfw.create_window(width, height, "MuJoCo Model Viewer", None, None)
    if not window:
        glfw.terminate()
        print("윈도우 생성 실패")
        return
    
    glfw.make_context_current(window)
    
    # 4) 렌더링을 위한 컨텍스트/씬/카메라/옵션 설정
    context = mujoco.MjrContext(model, mujoco.mjtFontScale.mjFONTSCALE_100)
    scene = mujoco.MjvScene(model, maxgeom=2000)
    
    cam = mujoco.MjvCamera()
    mujoco.mjv_defaultCamera(cam)
    
    opt = mujoco.MjvOption()
    mujoco.mjv_defaultOption(opt)
    
    # 카메라 대략적인 위치/시점 설정
    cam.distance = 3.0   # 모델로부터의 거리
    cam.azimuth = 90.0   # y축 기준 회전
    cam.elevation = -20.0
    
    # 5) 메인 루프
    while not glfw.window_should_close(window):
        # 시뮬레이션(옵션) — 단순히 정지 화면만 보고 싶다면 굳이 mj_step은 호출 안 해도 됩니다.
        # mujoco.mj_step(model, data)
        
        # 장면 갱신
        mujoco.mjv_updateScene(
            model, data, opt, None, cam,
            mujoco.mjtCatBit.mjCAT_ALL.value, scene
        )
        
        # 화면에 렌더링
        viewport = mujoco.MjrRect(0, 0, width, height)
        mujoco.mjr_render(viewport, scene, context)
        
        # 이벤트 처리
        glfw.swap_buffers(window)
        glfw.poll_events()
    
    # 종료 처리
    glfw.terminate()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} [MuJoCo XML path]")
        sys.exit(0)
    
    xml_file = sys.argv[1]
    main(xml_file)
