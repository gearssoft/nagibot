
# RTSP Stream Server

```bash
python server.py -f test.mp4 -p 21054 -m /test   
pm2 start server.py --name rtsp-simple --interpreter python -- -f test.mp4 -p 21054 -m /test


python server.py \
  -p 21054 \
  -s test.mp4:/test1 \
  -s test2.mp4:/test2

pm2 start server.py --name rtsp-simple --interpreter python -- -p 21054 -s test.mp4:/test1 -s test2.mp4:/test2
```
