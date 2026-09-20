from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

SCHEMA="n3w.kf096.pr437-177468e.boardb-usb-enum-readonly/1"
EXPECTED_PORT="/dev/cu.usbmodem14101"
PRODUCT_SOURCE_HEAD="177468e290a207f2fb7f6c554aedf60b61373b4d"
APPLICATION_SHA256="74f6b111d3af3b1247e6f367d3da10957846dbe6103e74fc507bc26e43065093"

def sha256_text(v:str)->str:
    return hashlib.sha256(v.encode()).hexdigest()

def run_optional(args:list[str])->tuple[int,str]:
    p=subprocess.run(args,text=True,capture_output=True,check=False)
    return p.returncode,(p.stdout or "")+(p.stderr or "")

def write_json(path:Path,payload:dict[str,object])->None:
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    path.chmod(0o600)

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--output",required=True)
    args=ap.parse_args()
    output=Path(args.output)

    candidates=sorted(glob.glob("/dev/cu.usbmodem*"))
    expected_present=os.path.exists(EXPECTED_PORT)

    owner_count=None
    lsof_available=False
    if expected_present:
        rc,out=run_optional(["lsof","-t","--",EXPECTED_PORT])
        if rc in (0,1):
            lsof_available=True
            owner_count=len({line.strip() for line in out.splitlines() if line.strip()})

    ioreg_available=False
    espressif_usb_match_count=None
    rc,out=run_optional(["ioreg","-p","IOUSB","-l","-w","0"])
    if rc==0:
        ioreg_available=True
        folded=out.casefold()
        espressif_usb_match_count=(
            folded.count("usb jtag/serial debug unit")
            + folded.count("espressif")
        )

    result={
        "schema":SCHEMA,
        "status":"PASS",
        "product_source_head":PRODUCT_SOURCE_HEAD,
        "application_sha256":APPLICATION_SHA256,
        "expected_port_present":expected_present,
        "expected_port_sha256":sha256_text(EXPECTED_PORT),
        "usbmodem_candidate_count":len(candidates),
        "usbmodem_candidate_path_hashes":[sha256_text(x) for x in candidates],
        "lsof_available":lsof_available,
        "expected_port_open_owner_count":owner_count,
        "ioreg_available":ioreg_available,
        "espressif_usb_match_count":espressif_usb_match_count,
        "board_reset":False,
        "serial_open":False,
        "flash_write":False,
        "nvs_write":False,
        "t1_access":False,
        "t1_mutation":False,
    }
    write_json(output,result)

    print("BOARD_B_USB_ENUM_READONLY_FORENSIC=PASS")
    print(f"EXPECTED_BOARD_B_USB_PATH_PRESENT={str(expected_present).lower()}")
    print(f"USBMODEM_CANDIDATE_COUNT={len(candidates)}")
    print("EXPECTED_PORT_OPEN_OWNER_COUNT="+("UNKNOWN" if owner_count is None else str(owner_count)))
    print(f"IOREG_AVAILABLE={str(ioreg_available).lower()}")
    print("ESPRESSIF_USB_MATCH_COUNT="+("UNKNOWN" if espressif_usb_match_count is None else str(espressif_usb_match_count)))
    print("BOARD_RESET=false")
    print("APPLICATION_SERIAL_OPEN=false")
    print("FLASH_WRITE=false")
    print("PRODUCT_NVS_WRITE=false")
    print("T1_ACCESS=false")
    print("T1_MUTATION=false")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
