# redSkeleton (Express)


## npm 모듈 새로 설치하기

```sh
npm i dotenv express fs-extra
npm i -D cross-env nodemon
```

## 사용법
반드시 클로닝 이후에 npm install을 한번 실행해주세요.  


```sh
npm install # 처음 한번만
copy .\sample.config.env .env

npm start # 배포용 실핼
npm run dev # 개발용 실행 

pm2 start npm --name "MMS" -- start # pm2 배포용 실행
pm2 restart MMS # pm2 재시작

pm2 start ecosystem.config.js

```

**ecosystem.config.cjs**

```js
module.exports = {
  apps: [
    {
      name: "MMS",
      cwd: "D:\\works\\nagibot\\Apps\\MMS", 
      script: "npm",
      args: "start",
      interpreter: "none", // npm은 node로 실행하지 않음
      env: {
        NODE_ENV: "production",
        PORT: 8080, // 필요시 포트 지정
      },
      autorestart: true,
      watch: true, // 코드 변경 시 자동 재시작 원하면 true
      max_memory_restart: "512M", // 메모리 초과 시 자동 재시작
      time: true, // 로그에 timestamp 포함
      error_file: "./logs/err.log",
      out_file: "./logs/out.log",
      log_date_format: "YYYY-MM-DD HH:mm:ss",
    },
  ],
};

``` 



## api auth 인증방법
auth 인증토큰을 헤더에 전달한다.  
```
auth-token : 5874  
```





## todo

* 웹에서 디랙토리와 파일목록을 구분해서 출력  
* 웹에서 파일읽기,쓰기 지우기 예제  






