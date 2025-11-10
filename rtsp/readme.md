
# RTSP Stream Server

```bash

python server.py -s test.mp4:/test -p 21054
pm2 start server.py --name rtsp-simple --interpreter python -- -s test.mp4:/test -p 21054


python server.py \
  -p 21054 \
  -s test.mp4:/test1 \
  -s test2.mp4:/test2

pm2 start server.py --name rtsp-simple --interpreter python -- -p 21054 -s test.mp4:/test1 -s test2.mp4:/test2

python server.py -s test.mp4:/testRGB -s test2.mp4:/testIR -p 21899
pm2 start server.py --name rtsp-simple --interpreter python -- -s test.mp4:/testRGB -s test2.mp4:/testIR -p 21899
```


## Access the streams
```
rtsp://ailab.miso.center:21899/testRGB
rtsp://ailab.miso.center:21899/testIR
```