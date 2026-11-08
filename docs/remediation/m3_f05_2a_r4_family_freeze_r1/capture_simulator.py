from pathlib import Path
import subprocess,sys
root=Path("/home/GodOfAgents/code/VAMS-testnet")
d=root/"docs/remediation/m3_f05_2a_r4_family_freeze_r1"
cmd=["bwrap","--unshare-net","--ro-bind","/","/","--tmpfs","/tmp","--ro-bind","/home/GodOfAgents/.cache","/home/GodOfAgents/.cache","--dev-bind","/dev","/dev","--proc","/proc","--setenv","HOME","/home/GodOfAgents","--chdir",str(root),"/home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python","-B","docs/remediation/m3_f05_2a_r4_family_freeze_r1/run_family.py"]
p=subprocess.run(cmd,cwd=root,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False)
(d/"SIMULATOR.stdout").write_bytes(p.stdout)
(d/"SIMULATOR.stderr").write_bytes(p.stderr)
(d/"SIMULATOR.exit").write_text(str(p.returncode)+"\n")
print("exit="+str(p.returncode))
if p.stdout: print(p.stdout.decode("utf-8",errors="replace"))
if p.stderr: print("stderr:\n"+p.stderr.decode("utf-8",errors="replace"))
raise SystemExit(p.returncode)
