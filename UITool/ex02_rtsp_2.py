#%% video sample for mp4
import cv2 as cv
import numpy as np


from PIL import Image
from IPython.display import display

from IPython.display import display
print( f"opencv version : {cv.__version__}")

#%%
#rtmp://210.99.70.120/live/cctv001.stream
# url = f'http://210.99.70.120:1935/live/cctv001.stream/playlist.m3u8' # 충청남도 천안시_교통정보 CCTV
url = "rtsp://210.99.70.120:1935/live/cctv001.stream"
# url = 'rtsp://ailab.miso.center:21054/test2'


#%%
cap = cv.VideoCapture(url)
if cap.isOpened() :
    print(f'open success {url}')
    ret, frame = cap.read()
    if ret is True:
        img_rgb = cv.cvtColor(frame, cv.COLOR_BGR2RGB)
        display( Image.fromarray(img_rgb) )
    else :
        print('capture failed')
    cap.release()
else :
    print(f'open failed {url}')

# %%
