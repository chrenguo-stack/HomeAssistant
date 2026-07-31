#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,os
from pathlib import Path
DECISION_ID='D1-H3N2-STAGE2D9R-G3R-D2-17-G13-PHYSICAL-EXECUTION-20260731-01'
def canonical(v:object)->str:return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
def main()->int:
 p=Path.home()/".local/state/greenhouse-stage2d9r/d2-17-g13-physical-decisions"/(DECISION_ID+".json")
 if not p.exists():return 0
 if not p.is_file() or p.is_symlink():raise SystemExit("PHYSICAL_DECISION_MARKER_NOT_REGULAR")
 v=json.loads(p.read_text(encoding="utf-8"))
 if not isinstance(v,dict) or v.get("decision_id")!=DECISION_ID:raise SystemExit("PHYSICAL_DECISION_MARKER_IDENTITY_DRIFT")
 v.pop("marker_sha256",None);v["marker_sha256"]=canonical(v);tmp=p.with_name(p.name+".finalize.tmp")
 if tmp.exists():raise SystemExit("PHYSICAL_DECISION_MARKER_FINALIZER_TMP_EXISTS")
 flags=os.O_WRONLY|os.O_CREAT|os.O_EXCL
 if hasattr(os,"O_NOFOLLOW"):flags|=os.O_NOFOLLOW
 fd=os.open(tmp,flags,0o600)
 try:
  with os.fdopen(fd,"w",encoding="utf-8",closefd=False) as f:json.dump(v,f,sort_keys=True,indent=2);f.write("\n");f.flush();os.fsync(f.fileno())
 finally:os.close(fd)
 os.replace(tmp,p);os.chmod(p,0o600);return 0
if __name__=="__main__":raise SystemExit(main())
