
import asyncio
from server.server import Server

from dotenv import load_dotenv
import os
load_dotenv()

# import torch
# print(torch.__version__)
# print(f'cuda is available {torch.cuda.is_available()}')


def main():
    # print("Hello from parkingeye!")
    port = int(os.getenv('PORT', 8282))
    ip = os.getenv('IP', '127.0.0.1')
    print(f"Start {ip}:{port}")

    try:
        _app = os.getenv('APP', 'server')

        if _app == 'server':
           
            
            _server = Server(host=ip, port=port)
            asyncio.run(_server.run())
        elif _app == 'client':

            from test_client import main as client_main
            
            asyncio.run(client_main(host=ip, port=port))
            
            
    except KeyboardInterrupt:
        print("\n[INFO] 서버 종료")


if __name__ == "__main__":
    main()
