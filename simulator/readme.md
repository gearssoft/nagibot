## 실행파일 만들기

```bash
pyinstaller --onefile --windowed car_simulator.py
```


## 시뮬레이터 사용법


- `--host`: 시뮬레이터가 바인딩할 IP 주소 (기본값: `0.0.0.0`)
- `--port`: 시뮬레이터가 바인딩할 포트 번호 (기본값: `5000`)
- `--send-hz`: 센서 상태 송신 빈도(Hz). 0.2 => 5초마다 1번 (기본값: `10.0`)
- `--send-interval-ms`: 송신 간격(ms). 지정 시 --send-hz 보다 우선 (기본값: `None`)
- `--tick-hz`: 내부 로직 틱(Hz) (기본값: `20.0`)


**참고**

```python
p = argparse.ArgumentParser()
p.add_argument('--host', default='0.0.0.0')
p.add_argument('--port', type=int, default=5000)
p.add_argument('--send-hz', type=float, default=10.0, help='센서 상태 송신 빈도(Hz). 0.2 => 5초마다 1번')
p.add_argument('--send-interval-ms', type=float, default=None, help='송신 간격(ms). 지정 시 --send-hz 보다 우선')
p.add_argument('--tick-hz', type=float, default=20.0, help='내부 로직 틱(Hz)')
args = p.parse_args()

```
