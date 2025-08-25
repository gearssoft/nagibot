# set_mujoco_gl_runtime_hook.py
import os
os.environ.setdefault('MUJOCO_GL', 'glfw')
# 필요시 활성화
# os.environ.setdefault('GLFW_LIBRARY_NAME', 'glfw3.dll')
