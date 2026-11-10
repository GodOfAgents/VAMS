#!/bin/sh
# ruleid: vams-uvicorn-cli-proxy-headers-enabled
uvicorn gateway.server:app --host 127.0.0.1 --port 8000
# ok: vams-uvicorn-cli-proxy-headers-enabled
uvicorn gateway.server:app --host 127.0.0.1 --port 8000 --no-proxy-headers
