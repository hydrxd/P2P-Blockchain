import subprocess
import sys
import time
import os

NUM_NODES = 3
BASE_PORT = 8000

if len(sys.argv) > 1:
    NUM_NODES = int(sys.argv[1])
if len(sys.argv) > 2:
    BASE_PORT = int(sys.argv[2])

processes = []
for i in range(NUM_NODES):
    port = BASE_PORT + i
    env = dict(**os.environ, NODE_ADDRESS=f"127.0.0.1:{port}")
    cmd = [sys.executable, "-m", "uvicorn", "node:app", "--port", str(port), "--reload"]
    p = subprocess.Popen(cmd, env=env)
    processes.append(p)
    print(f"Started node on port {port}")
    time.sleep(1)

try:
    for p in processes:
        p.wait()
except KeyboardInterrupt:
    for p in processes:
        p.terminate() 