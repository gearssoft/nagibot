# Project Nagi-Bot 

## Description

이 프로잭트는 비살상 정찰 목정의 자율주행 로봇 관제용 소프트웨어입니다.

## Project Installation

```bash
pip install -r requirements.txt
``` 

## launch.json 


lauch.json 파일은 다음과 같이 설정합니다.  

```json
{
    
    "configurations": [
        {
            "type": "debugpy",
            "request": "launch",
            "name": "Launch Current Venv",
            "python": "${workspaceFolder}/.venv/bin/python", // 가상환경을 사용하고 있다면 python 경로를 가상환경의 python 경로로 설정해야 합니다.  
            //"program": "${workspaceFolder}/${input:programPath}",
            "program": "${file}",
            "cwd": "${fileDirname}", //cwd는 현재 파일이 있는 디렉토리로 설정해야 합니다.  
            "console": "integratedTerminal",
        },
        {
            "name": "Python 디버거: 현재 파일",
            "type": "debugpy",
            "request": "launch",
            "program": "${file}",
            "console": "integratedTerminal"
        }
    ],
    "inputs": [
        {
            "type": "promptString",
            "id": "programPath",
            "description": "Enter the relative path to the main Python file"
        }
    ]
}
```
