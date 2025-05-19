
# RTSP Stream Server

```bash
python server.py -f test.mp4 -p 21054 -m /test   
pm2 start server.py --name rtsp-simple --interpreter python -- -f test.mp4 -p 21054 -m /test
```
