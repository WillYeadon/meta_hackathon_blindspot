"""Run with `python run.py`; one worker owns the background experiment queue."""
import argparse
import uvicorn

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    uvicorn.run("blindspot.app:app", host=args.host, port=args.port, workers=1)
