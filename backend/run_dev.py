import argparse
import os

import uvicorn

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--port", type=int, default=None)
    parser.add_argument("--host", type=str, default=os.environ.get("HOST", "0.0.0.0"))
    args, _ = parser.parse_known_args()
    port = args.port or int(os.environ.get("PORT", "5180"))
    uvicorn.run("app:app", host=args.host, port=port, reload=True, log_level="info")
