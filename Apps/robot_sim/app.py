from server.server import Server

import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

if __name__ == "__main__":

    try:

        ip = os.getenv("IP", "127.0.0.1")
        port = int(os.getenv("PORT", 8282))

        server = Server(host=ip, port=port)
        asyncio.run(server.run())
    except Exception as e:
        print(f"Error: {e}")
    finally:
        print("Server terminated.")