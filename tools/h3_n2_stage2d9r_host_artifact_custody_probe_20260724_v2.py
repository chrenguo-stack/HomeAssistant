#!/usr/bin/env python3
"""Stage2D9R V2 read-only public Artifact and private-custody metadata probe.

V2 binds consumed markers by their exact full-file SHA-256 and validates only
non-secret marker shape fields. The redundant inner authorization-record digest
cross-binding is deliberately deferred to a separate exact private-content
authorization.
"""
from __future__ import annotations
import argparse, hashlib, json, os, re, stat, sys, tarfile
from pathlib import Path
from typing import Any

S="H3/N2 Stage 2D-9R G3R"; H40=re.compile(r"^[0-9a-f]{40}$"); H64=re.compile(r"^[0-9a-f]{64}$")
PY="4e28e811a89aeac6eed668ae641c7f85f5831e42e8dc6cd9a85a3bcc032ec46a"
U="3650d44f8761f21dc1931fbd9b6ba6a1d9da92ffa469b3d4f98ee5411a6809e3"
CA="cfcb6638ed61731270f3bf8e9e262c1512fbca8ff34d4b08b62186453233e963"
CAND="f22144e37372b883b7a38d07eff2980a865108cf7c8fed9bfdb9f198a030b5c5"
ERASED="71189f7fb6aed638640078fba3a35fda6c39c8962e74dcc75935aac948da9063"
IMM={
"tar":"5dbe763fe411728533018dd324075f5287ee3542f8351113d54ec80a7042f1d3",
"record":"1217e03ae541cd0a11139ab2bf502162d0ecb62769e038868157e7488a888091",
"sha_file":"ef7ed1c06aecd53d5a7560bcdd218b13dcc565e01bb1f38a69481a9a22a9ba07",
"source":"c9e8447c24b0f09f3eac3f56791f2346e8aa5d61",
"binding":"b39f20c55b865ec87eb650d620fd1a82b930c1ad",
"application":"7651a6476cd48dda6aa5e400695e126b91141c95fca5b74d879f65f2058d1630",
"bootloader":"330c91761398f5f38ede9a41458ada73573c9e53c8b562087219fa36823bf9dc",
"partition":"b3964cbbd811d5fa5866638585fa410b53fc74e70a8f92491f43fce0b7a70268",
"merged":"ea6af469ad7ae103d40a551f482fc18d1f2afc9ed75933481f1802f0a7b2916f",
"payload_json":"eac299e28a8d2e658b6c1302046e3ae946912522eb0cf3dbd97c17f18ba57938"}
REC={"tar":"c1ed8e5f00b17cbe5bab30aec75d2e8637986b9c19b2389b761bebf3fc0b8d8b",
"file":"88ac19e9baa1c00581adfb89ad5f0b00a0cf5e4044fe330b4e5670615bf5df4a",
"manifest":"fe82c458533953df4c86966d047d1f66b59da15e5299b3953135702236d68690",
"source":"f312f8580d9f4312f4dd1429b2d7755e1c550636"}
CMD={"rel":".local/state/greenhouse-stage2d9r/private-command-material-tlsvalid01",
"root":"ef5f79be168fff686cabcc91fdc4109918d75d3311da1209dd8d0e381804006e",
"private":"cda5b1604200045fec0db45e46f9c441e1bde10f2e5a57f8c98ee2d14b5f9a75",
"public":"91c10168174438fc30b3dce087a6b75e24375b87b4262bafddb5b2822ee16d23",
"package":"cc9086c20781007655c498b78ff1ce7af3316db0c02edbae2440d177d7fdfbb5",
"exec":"283b6bf20bbeda03181a719ffd638f3a4b3a40e86c047aff9f4280df29763327",
"impl":"3d3b67cac008adf30e90a51e891d0dd53b36df69",
"source":"9dd8ca9e0b3139bfd187eb7a1dfa38485a9eb2fd",
"u101":"7461c0396a7be9fc99d1e880fdfc386054f003b4a64f9e758e6b826f93769314",
"u102":"1fc51b7338adc56b00b38795173b805b7408e7aafa4e0315e7553dc5898779a9"}
PKI={"rel":".local/state/greenhouse-stage2d9r/private-pki-tlsvalid01",
"root":"4cd43ee4b2df177bd99c32d3904dbe1e1df890aa14c6b6714a6b4f7ae4024868",
"private":"59814b825cd2df4ac7f0e3eb137798af4efdbbed4da9d627fe8ad98144be8687",
"public":"93bb071a5bf6f58472ac9e3891c2330dd9de6f05410824ad2fb51829267b4540",
"config":"01c10996c8dc8c7de9a8284284cecbd6ca25f03089297896984bd09e1fad7cf0",
"ca":CA,"broker":"57ea55a007810ce86dd8723d1eabb73047814481e02dfa37b9ce965fac657fe1",
"chain":"8d567a5db699a7a3f7d7ba7904d917cacebcfd9268f44af699a384afe763afda",
"package":"0632b37a70aa2eae416c48ffa9420a8f1e13788c22a7d12e211f77cf6e78a267",
"marker":"fbe03088de17b8db4d8b048e1985d571ca9f54d3add9b9fc3fce1735c9bec261"}
AUTH=".local/state/greenhouse-stage2d9r/authorizations"
class E(RuntimeError): pass
def q(x:bool,m:str)->None:
    if not x: raise E(m)
def hb(b:bytes)->str:return hashlib.sha256(b).hexdigest()
def hf(p:Path)->str:return hb(p.read_bytes())
def mode(p:Path)->str:return f"{stat.S_IMODE(p.stat().st_mode):04o}"
def secret_meta(p:Path,size:int|None=None)->None:
    q(p.exists() and p.is_file() and not p.is_symlink(),"private file invalid")
    q(mode(p)=="0600","private file mode mismatch")
    if size is not None:q(p.stat().st_size==size,"private file size mismatch")
def root_meta(p:Path,digest:str)->None:
    q(hb(str(p).encode())==digest,"custody root digest mismatch")
    q(p.exists() and p.is_dir() and not p.is_symlink(),"custody root invalid")
    q(mode(p)=="0700","custody root mode mismatch")
def safe_json(p:Path,digest:str)->dict[str,Any]:
    q(p.is_file() and not p.is_symlink() and mode(p)=="0600","descriptor invalid")
    b=p.read_bytes();q(hb(b)==digest,"descriptor digest mismatch")
    v=json.loads(b);q(isinstance(v,dict),"descriptor type invalid");return v
def sums(b:bytes)->dict[str,str]:
    r={}
    for line in b.decode().splitlines():
        if not line:continue
        d,n=line.split("  ",1);q(H64.fullmatch(d) is not None and n not in r,"SHA256SUMS invalid");r[n]=d
    return r
def untar(p:Path,names:set[str])->dict[str,bytes]:
    out={}
    with tarfile.open(p,"r") as a:
        ms=a.getmembers();q({m.name for m in ms}==names,"tar members mismatch")
        for m in ms:
            q(m.isfile() and m.mode==0o600 and m.uid==0 and m.gid==0 and m.mtime==0,"tar metadata mismatch")
            f=a.extractfile(m);q(f is not None,"tar member unreadable");out[m.name]=f.read()
    return out
def immutable(r:Path)->dict[str,str]:
    t=r/"stage2d9r-g3r-immutable-payload-v1.tar";rec=r/"build-record.json";sf=r/"payload-tar.sha256"
    q(hf(t)==IMM["tar"] and hf(rec)==IMM["record"] and hf(sf)==IMM["sha_file"],"immutable outer digest mismatch")
    q(sf.read_text().strip()==IMM["tar"],"immutable digest file mismatch")
    ns={"SHA256SUMS","application.bin","bootloader.bin","firmware-payload.json","merged-image.bin","partition-table.bin"}
    f=untar(t,ns);s=sums(f["SHA256SUMS"]);q(set(s)==ns-{"SHA256SUMS"},"immutable sums coverage")
    for n,d in s.items():q(hb(f[n])==d,f"immutable digest mismatch:{n}")
    q(s["application.bin"]==IMM["application"] and s["bootloader.bin"]==IMM["bootloader"],"immutable firmware digest mismatch")
    q(s["partition-table.bin"]==IMM["partition"] and s["merged-image.bin"]==IMM["merged"],"immutable image digest mismatch")
    q(s["firmware-payload.json"]==IMM["payload_json"],"immutable payload JSON mismatch")
    p=json.loads(f["firmware-payload.json"]);q(p["source_sha"]==IMM["source"] and p["build_binding"]==IMM["binding"],"immutable binding mismatch")
    q(p["candidate_bindings"]=={"broker_host":"stage2d9r.local","broker_tls_server_name":"stage2d9r.local","ca_pem_sha256":CA,"candidate_digest_sha256":CAND,"unlock_digest_sha256":U},"candidate binding mismatch")
    return {"payload_sha256":IMM["tar"],"application_sha256":IMM["application"],"merged_sha256":IMM["merged"],"source_sha":IMM["source"]}
def recovery(r:Path)->dict[str,str]:
    ss=sums((r/"SHA256SUMS").read_bytes())
    for n,d in ss.items():q(hf(r/n)==d,f"recovery outer digest mismatch:{n}")
    t=r/"stage2d9r-g3r-recovery-payload-v1.tar";mp=r/"stage2d9r_recovery_artifact_manifest_20260724_v1.json"
    q(hf(t)==REC["tar"] and hf(mp)==REC["file"],"recovery frozen digest mismatch")
    ns={"RECOVERY_CONTRACT.md","SHA256SUMS","recovery-artifact-descriptor.json","recovery-authorization-manifest.template.json","test-partition-erased.bin"}
    f=untar(t,ns);si=sums(f["SHA256SUMS"]);q(set(si)==ns-{"SHA256SUMS"},"recovery sums coverage")
    for n,d in si.items():q(hb(f[n])==d,f"recovery member digest mismatch:{n}")
    q(f["test-partition-erased.bin"]==b"\xff"*65536 and hb(f["test-partition-erased.bin"])==ERASED,"erased image mismatch")
    m=json.loads(mp.read_bytes());q(m["source_sha"]==REC["source"] and m["artifact"]["payload_tar_sha256"]==REC["tar"],"recovery binding mismatch")
    q(m["artifact"]["manifest_sha256"]==REC["manifest"] and m["reproducibility"]["payloads_byte_identical"] is True,"recovery reproducibility mismatch")
    for k in ("execution_authorized","recovery_authorized","board_operation_authorized","serial_operation_authorized","flash_operation_authorized","physical_nvs_operation_authorized","network_operation_authorized","broker_operation_authorized","firmware_flash_authorized","prepare_authorized","verify_authorized","activate_authorized","cleanup_authorized","production_operation_authorized","ready_authorized","merge_authorized","release_authorized","deployment_authorized"):q(m[k] is False,f"recovery authorization expanded:{k}")
    return {"payload_sha256":REC["tar"],"manifest_sha256":REC["manifest"],"erased_sha256":ERASED,"source_sha":REC["source"]}
def marker(p:Path,d:str,aid:str,status:str)->dict[str,object]:
    v=safe_json(p,d)
    q(
        v.get("authorization_id")==aid
        and v.get("status")==status
        and v.get("one_shot") is True
        and v.get("replay_permitted") is False
        and v.get("secret_values_included") is False,
        "marker binding mismatch",
    )
    record=v.get("record_sha256")
    q(isinstance(record,str) and H64.fullmatch(record) is not None,"marker record shape mismatch")
    return {
        "authorization_id":aid,
        "status":status,
        "marker_file_sha256":d,
        "record_sha256_shape_valid":True,
        "record_cross_binding":"DEFERRED_REQUIRES_SEPARATE_EXACT_AUTHORIZATION",
    }
def command(home:Path)->dict[str,object]:
    r=(home/CMD["rel"]).resolve(strict=False);root_meta(r,CMD["root"]);secret_meta(r/"unlock-token.hex",65)
    d=safe_json(r/"private-command-material-descriptor.json",CMD["private"]);p=safe_json(r/"public-command-material-descriptor.redacted.json",CMD["public"])
    q(d["source_sha"]==CMD["source"] and d["implementation_binding"]==CMD["impl"] and d["custody_root"]==str(r),"command descriptor binding mismatch")
    q(d["unlock_token"]["relative_path"]=="unlock-token.hex" and d["unlock_token"]["mode"]=="0600" and d["unlock_token"]["unlock_digest_sha256"]==U,"command token metadata mismatch")
    q(d["public_descriptor_sha256"]==CMD["public"] and d["execution_binding_sha256"]==CMD["exec"],"command descriptor digest binding mismatch")
    q(p["unlock_digest_sha256"]==U and p["execution_binding_sha256"]==CMD["exec"],"command public binding mismatch")
    a=(home/AUTH).resolve(strict=False);q(a.is_dir() and mode(a)=="0700","authorization directory invalid")
    markers=[
        marker(a/"U1-H3N2-STAGE2D9R-COMMAND-MATERIAL-20260724-01.consumed.json",CMD["u101"],"U1-H3N2-STAGE2D9R-COMMAND-MATERIAL-20260724-01","CONSUMED_FAILED"),
        marker(a/"U1-H3N2-STAGE2D9R-COMMAND-MATERIAL-20260724-02.consumed.json",CMD["u102"],"U1-H3N2-STAGE2D9R-COMMAND-MATERIAL-20260724-02","CONSUMED"),
    ]
    return {"root_digest":CMD["root"],"private_descriptor_sha256":CMD["private"],"public_descriptor_sha256":CMD["public"],"package_sha256":CMD["package"],"unlock_digest_sha256":U,"consumed_markers":markers,"token_content_read":False}
def pki(home:Path)->dict[str,object]:
    r=(home/PKI["rel"]).resolve(strict=False);root_meta(r,PKI["root"])
    for n in ("root-ca.key.pem","broker.key.pem","mosquitto.password","mosquitto.stage2d9r.conf","mosquitto.stage2d9r.acl"):secret_meta(r/n)
    for n,dig in {"root-ca.cert.pem":PKI["ca"],"broker.cert.pem":PKI["broker"],"broker.fullchain.pem":PKI["chain"],"public-descriptor.redacted.json":PKI["public"],"isolated-broker-public-config.redacted.json":PKI["config"]}.items():
        q((r/n).is_file() and not (r/n).is_symlink() and mode(r/n)=="0600" and hf(r/n)==dig,f"PKI public binding mismatch:{n}")
    d=safe_json(r/"private-custody-descriptor.json",PKI["private"]);p=safe_json(r/"public-descriptor.redacted.json",PKI["public"])
    q(d["custody_root"]==str(r) and d["package_sha256"]==PKI["package"] and d["public_descriptor_sha256"]==PKI["public"] and d["candidate_digest_sha256"]==CAND,"PKI descriptor binding mismatch")
    q(p["public_material"]["ca_pem_sha256"]==CA and p["public_material"]["candidate_digest_sha256"]==CAND,"PKI public binding mismatch")
    a=(home/AUTH).resolve(strict=False)
    consumed=marker(a/"U1-H3N2-STAGE2D9R-PRIVATE-PKI-20260723-01.consumed.json",PKI["marker"],"U1-H3N2-STAGE2D9R-PRIVATE-PKI-20260723-01","CONSUMED")
    return {"root_digest":PKI["root"],"private_descriptor_sha256":PKI["private"],"public_descriptor_sha256":PKI["public"],"package_sha256":PKI["package"],"ca_pem_sha256":CA,"candidate_digest_sha256":CAND,"consumed_marker":consumed,"private_key_content_read":False,"password_content_read":False}
def main()->int:
    a=argparse.ArgumentParser();a.add_argument("--package-root",type=Path,default=Path(__file__).resolve().parent);a.add_argument("--home",type=Path,default=Path.home());a.add_argument("--public-artifacts-only",action="store_true");x=a.parse_args()
    failure_stage="ARGUMENT_RESOLUTION"
    try:
        root=x.package_root.expanduser().resolve(strict=True);home=x.home.expanduser().resolve(strict=True)
        failure_stage="PYTHON_TOOLCHAIN"
        if not x.public_artifacts_only:q(hf(Path(sys.executable).resolve(strict=True))==PY and sys.version.startswith("3.11.9 "),"Python toolchain changed")
        failure_stage="IMMUTABLE_ARTIFACT"
        im=immutable(root/"public-artifacts/immutable")
        failure_stage="RECOVERY_ARTIFACT"
        reco=recovery(root/"public-artifacts/recovery")
        failure_stage="COMMAND_CUSTODY"
        c="NOT_EXECUTED_PUBLIC_ARTIFACT_MODE" if x.public_artifacts_only else command(home)
        failure_stage="PKI_CUSTODY"
        pk="NOT_EXECUTED_PUBLIC_ARTIFACT_MODE" if x.public_artifacts_only else pki(home)
        out={"schema":"gh.h3.n2.stage2d9r-host-artifact-custody-preauth-probe/2","stage":S,"result":"PASS_PUBLIC_ARTIFACTS_ONLY" if x.public_artifacts_only else "PASS_READ_ONLY_PREAUTH","python_executable_sha256":PY,"immutable_artifact":im,"recovery_artifact":reco,"command_custody":c,"pki_custody":pk,"private_material_content_binding":"NOT_EXECUTED_REQUIRES_SEPARATE_EXACT_AUTHORIZATION","marker_record_cross_binding":"DEFERRED_REQUIRES_SEPARATE_EXACT_AUTHORIZATION","private_content_read":False,"private_paths_included":False,"secret_values_included":False,"repository_required":False,"network_operation":False,"broker_started":False,"board_operation":False,"serial_operation":False,"flash_operation":False,"physical_nvs_operation":False,"prepare_executed":False,"verify_executed":False}
        print("HOST_ARTIFACT_CUSTODY_PREAUTH_PROBE=PASS");print(json.dumps(out,sort_keys=True));return 0
    except Exception as e:
        print("HOST_ARTIFACT_CUSTODY_PREAUTH_PROBE=FAIL");print(f"FAILURE_STAGE={failure_stage}");print(f"FAILURE_CLASS={type(e).__name__}");print(f"FAILURE_MESSAGE={e}")
        for k in ("PRIVATE_CONTENT_READ","PRIVATE_PATHS_INCLUDED","SECRET_VALUES_INCLUDED","NETWORK_OPERATION","BROKER_STARTED","BOARD_OPERATION","SERIAL_OPERATION","FLASH_OPERATION"):print(f"{k}=false")
        return 2
if __name__=="__main__":raise SystemExit(main())
