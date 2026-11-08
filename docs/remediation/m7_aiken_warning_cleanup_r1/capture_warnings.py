from __future__ import annotations

import hashlib
import json
import pathlib
import pty
import re
import select
import subprocess
import tempfile
import time

ROOT = pathlib.Path("/home/GodOfAgents/code/VAMS-testnet")
CARDANO = ROOT / "cardano"
TOOL = pathlib.Path("/home/GodOfAgents/vams-evidence/toolchains/aiken-1.1.21/unpacked/aiken-x86_64-unknown-linux-musl/aiken")
OUT = pathlib.Path(__file__).resolve().parent / "WARNING_DIAGNOSTIC.json"
TRANSCRIPT = pathlib.Path(__file__).resolve().parent / "WARNING_DIAGNOSTIC.txt"
ARGS = ["check", "--deny", "--seed", "20260711", "--max-success", "250"]

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def inventory() -> tuple[int, str]:
    rows=[]
    for path in sorted(CARDANO.rglob("*")):
        if path.is_file() and not path.is_symlink() and "build" not in path.relative_to(CARDANO).parts:
            rows.append((path.relative_to(CARDANO).as_posix(), sha(path.read_bytes())))
    digest=hashlib.sha256()
    for name, value in rows:
        digest.update(name.encode()+b"\0"+value.encode()+b"\n")
    return len(rows), digest.hexdigest()

def main() -> int:
    before_count, before_hash = inventory()
    bash = "cp -a . /tmp/vams-cardano-warning-probe && cd /tmp/vams-cardano-warning-probe && " + str(TOOL) + " " + " ".join(ARGS)
    command=["bwrap","--ro-bind","/","/","--tmpfs","/tmp","--dev-bind","/dev","/dev","--proc","/proc","--unshare-net","--chdir",str(CARDANO),"/bin/bash","-lc",bash]
    master,slave=pty.openpty()
    env={**__import__("os").environ,"TERM":"xterm-256color","PYTHONDONTWRITEBYTECODE":"1"}
    proc=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=slave,stderr=slave,env=env,close_fds=True)
    __import__("os").close(slave)
    chunks=[]
    deadline=time.monotonic()+600
    while True:
        ready,_,_=select.select([master],[],[],0.2)
        eof=False
        if ready:
            try: data=__import__("os").read(master,65536)
            except OSError: data=b""; eof=True
            if data: chunks.append(data)
            else: eof=True
        if proc.poll() is not None and eof:
            break
        if time.monotonic()>deadline:
            proc.kill(); proc.wait(); raise TimeoutError("Aiken warning capture exceeded 600 seconds")
    __import__("os").close(master)
    raw=b"".join(chunks)
    text=raw.decode("utf-8",errors="replace")
    clean=re.sub(r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\))", "", text).replace("\r", "")
    lines=clean.splitlines()
    warning_lines=sorted({line.strip() for line in lines if re.search(r"warning|warn|uncertain",line,re.I)})
    diagnostic_lines=sorted({line.strip() for line in lines if re.search(r"warning|warn|uncertain|error|deprecated",line,re.I)})
    warning_context=[]
    context_indexes=set()
    for index,line in enumerate(lines):
        if re.search(r"warning|uncertain",line,re.I):
            context_indexes.update(range(max(0,index-2),min(len(lines),index+3)))
    warning_context=[lines[index] for index in sorted(context_indexes)]
    summary_match=re.search(r"Summary\s+(\d+)\s+checks,\s+(\d+)\s+errors,\s+(\d+)\s+warnings",clean,re.I)
    after_count,after_hash=inventory()
    TRANSCRIPT.write_text(clean,encoding="utf-8")
    result={
      "schema":"m7-aiken-warning-pty-diagnostic-v1",
      "command":["aiken",*ARGS],
      "tool":{"path":str(TOOL),"version":"v1.1.21+42babe5","sha256":sha(TOOL.read_bytes())},
      "isolation":"Canonical Cardano tree read-only; fresh tmpfs project copy; network namespace disabled; no tools or dependencies fetched by this runner.",
      "source":{"file_count_before":before_count,"sha256_before":before_hash,"file_count_after":after_count,"sha256_after":after_hash,"unchanged":before_count==after_count and before_hash==after_hash},
      "exit_code":proc.returncode,
      "summary": {"checks":int(summary_match.group(1)),"errors":int(summary_match.group(2)),"warnings":int(summary_match.group(3))} if summary_match else None,
      "warning_line_count":len(warning_lines) if warning_lines else None,
      "warning_lines":warning_lines[:50],
      "warning_context":warning_context[:160],
      "diagnostic_lines":diagnostic_lines[:80],
      "capture_note":None if warning_lines else "No warning lines extracted from pseudo-terminal output; count/text are unavailable and not asserted.",
      "raw_output_sha256":sha(raw),
      "raw_output_retained":False,
      "sanitized_transcript":"WARNING_DIAGNOSTIC.txt",
      "sanitized_transcript_sha256":sha(clean.encode()),
      "sanitized_transcript_retained":True
    }
    OUT.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:result[k] for k in ("exit_code","summary","warning_line_count","warning_lines","warning_context","diagnostic_lines","capture_note","source")},indent=2))
    return 0 if result["source"]["unchanged"] else 3

if __name__=="__main__":
    raise SystemExit(main())
