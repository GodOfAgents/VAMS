from pathlib import Path
import subprocess
root=Path("/home/GodOfAgents/code/VAMS-testnet")
d=root/"docs/remediation/m3_f05_2a_r4_family_freeze_r1"
cmd=["/home/GodOfAgents/vams-evidence/toolchains/vams-py312/bin/python","-B",str(d/"freeze_family.py")]
p=subprocess.run(cmd,cwd=root,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False)
(d/"COORDINATOR.stdout").write_bytes(p.stdout)
(d/"COORDINATOR.stderr").write_bytes(p.stderr)
(d/"COORDINATOR.exit").write_text(str(p.returncode)+"\n")
print("exit="+str(p.returncode))
raise SystemExit(p.returncode)
