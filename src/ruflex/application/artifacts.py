from __future__ import annotations
import hashlib, json, os, re, sqlite3, tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, ValidationError
class ArtifactIntegrityError(RuntimeError): pass
class ArtifactMetadata(BaseModel):
 model_config=ConfigDict(extra="forbid"); media_type:str; source_kind:Literal["upload","generated","imported","external"]; original_name:str|None=None; source_uri:str|None=None; parent_artifacts:list[str]=Field(default_factory=list); producer:dict[str,str]|None=None
class ArtifactRef(BaseModel): sha256:str=Field(pattern=r"^[0-9a-f]{64}$")
class ArtifactRecord(ArtifactMetadata): schema_version:int=1; sha256:str; size_bytes:int; relative_blob_path:str; created_at:datetime
class ArtifactVerification(BaseModel): sha256:str; valid:bool; actual_sha256:str|None=None; message:str
class IndexReport(BaseModel): artifact_count:int
class ArtifactStore:
 def __init__(self,project_root:Path):
  self.root=Path(project_root).resolve(); self.blob_root=self.root/"artifacts"/"sha256"; self.metadata_root=self.root/"objects"/"artifacts"; self.index_path=self.root/"artifacts"/"index.sqlite"; self.blob_root.mkdir(parents=True,exist_ok=True); self.metadata_root.mkdir(parents=True,exist_ok=True)
 def ingest_bytes(self,data:bytes,*,metadata:ArtifactMetadata)->ArtifactRef:
  digest=hashlib.sha256(data).hexdigest(); blob=self._blob(digest); record=self._record(digest)
  if blob.exists() and hashlib.sha256(blob.read_bytes()).hexdigest()!=digest: raise ArtifactIntegrityError(f"Existing artifact blob hash mismatch: {digest}")
  if not blob.exists(): self._write(blob,data)
  payload=ArtifactRecord(**metadata.model_dump(),sha256=digest,size_bytes=len(data),relative_blob_path=str(blob.relative_to(self.root)),created_at=datetime.now(timezone.utc))
  if not record.exists():
   try:self._write(record,json.dumps(payload.model_dump(mode="json"),sort_keys=True).encode())
   except Exception:
    if blob.exists() and not record.exists(): blob.unlink()
    raise
  self.rebuild_index(); return ArtifactRef(sha256=digest)
 def ingest_file(self,path:Path,*,metadata:ArtifactMetadata)->ArtifactRef:
  path=Path(path)
  if not path.is_file() or path.is_symlink(): raise ArtifactIntegrityError("Artifact source must be a regular non-symlink file.")
  return self.ingest_bytes(path.read_bytes(),metadata=metadata)
 def verify(self,reference:ArtifactRef)->ArtifactVerification:
  blob=self._blob(reference.sha256); record_path=self._record(reference.sha256)
  if not blob.is_file() or blob.is_symlink(): return ArtifactVerification(sha256=reference.sha256,valid=False,message="Artifact blob is missing or unsafe.")
  actual=hashlib.sha256(blob.read_bytes()).hexdigest()
  if actual!=reference.sha256: return ArtifactVerification(sha256=reference.sha256,actual_sha256=actual,valid=False,message="Artifact blob hash mismatch.")
  if not record_path.is_file() or record_path.is_symlink(): return ArtifactVerification(sha256=reference.sha256,actual_sha256=actual,valid=False,message="Artifact metadata is missing or unsafe.")
  try:
   record=ArtifactRecord.model_validate_json(record_path.read_text(encoding="utf-8"))
   expected_path=str(blob.relative_to(self.root))
   if record.sha256!=reference.sha256 or record.size_bytes!=blob.stat().st_size or record.relative_blob_path!=expected_path:
    return ArtifactVerification(sha256=reference.sha256,actual_sha256=actual,valid=False,message="Artifact metadata does not match the canonical blob identity.")
  except (OSError, ValidationError, ValueError):
   return ArtifactVerification(sha256=reference.sha256,actual_sha256=actual,valid=False,message="Artifact metadata is malformed.")
  return ArtifactVerification(sha256=reference.sha256,actual_sha256=actual,valid=True,message="Artifact verified.")
 def open(self,reference:ArtifactRef):
  result=self.verify(reference)
  if not result.valid: raise ArtifactIntegrityError(result.message)
  return self._blob(reference.sha256).open("rb")
 def materialize(self,reference:ArtifactRef,destination:Path)->Path:
  target=(self.root/destination).resolve() if not Path(destination).is_absolute() else Path(destination).resolve()
  try:target.relative_to(self.root)
  except ValueError as e: raise ArtifactIntegrityError("Materialization destination escapes project root.") from e
  if target.exists(): raise ArtifactIntegrityError("Materialization destination already exists.")
  with self.open(reference) as f:self._write(target,f.read())
  return target
 def rebuild_index(self)->IndexReport:
  records=sorted(self.metadata_root.glob("*.json")); temp=self.index_path.with_suffix(".tmp.sqlite"); temp.unlink(missing_ok=True); c=sqlite3.connect(temp)
  try:
   c.execute("create table artifacts (sha256 text primary key,size_bytes integer,media_type text,source_kind text)")
   for p in records:
    r=ArtifactRecord.model_validate_json(p.read_text()); c.execute("insert into artifacts values (?,?,?,?)",(r.sha256,r.size_bytes,r.media_type,r.source_kind))
   c.commit()
  finally:c.close()
  os.replace(temp,self.index_path); return IndexReport(artifact_count=len(records))
 def list_records(self)->list[ArtifactRecord]:
  return [ArtifactRecord.model_validate_json(path.read_text(encoding="utf-8")) for path in sorted(self.metadata_root.glob("*.json"))]
 def _blob(self,digest:str)->Path:
  if not re.fullmatch(r"[0-9a-f]{64}",digest):raise ArtifactIntegrityError("Invalid artifact SHA-256.")
  return self.blob_root/digest[:2]/digest
 def _record(self,digest:str)->Path:return self.metadata_root/f"{digest}.json"
 @staticmethod
 def _write(path:Path,data:bytes):
  path.parent.mkdir(parents=True,exist_ok=True); fd,name=tempfile.mkstemp(prefix=".artifact-",dir=path.parent); temp=Path(name)
  try:
   with os.fdopen(fd,"wb") as h:h.write(data);h.flush();os.fsync(h.fileno())
   os.replace(temp,path)
  finally:temp.unlink(missing_ok=True)
