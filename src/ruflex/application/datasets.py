from __future__ import annotations
import hashlib, json, os, tempfile
from pathlib import Path
from typing import Literal
import pandas as pd
from pydantic import BaseModel, Field
from ruflex.application.artifacts import ArtifactMetadata, ArtifactRef, ArtifactStore
class DatasetConfirmationError(ValueError): pass
class FeatureSpec(BaseModel): name:str; semantic_type:str; dtype:str; nullable:bool; categories:list[str]|None=None
class DatasetProfile(BaseModel): columns:list[FeatureSpec]; row_count:int; source_artifact_sha256:str; fingerprint:str; id_candidates:list[str]
class SchemaComparison(BaseModel): compatible:bool; missing_columns:list[str]; unexpected_columns:list[str]
class DatasetContract(BaseModel):
 dataset_fingerprint:str; source_artifact_sha256:str; target:str; task:Literal['regression','binary_classification','multiclass_classification']; feature_columns:list[str]; id_columns:list[str]=Field(default_factory=list); source_format:Literal['csv','xlsx']='csv'
 def compare_schema(self,frame:pd.DataFrame):
  expected=set(self.feature_columns)|set(self.id_columns)|{self.target}; actual=set(frame.columns); return SchemaComparison(compatible=expected==actual,missing_columns=sorted(expected-actual),unexpected_columns=sorted(actual-expected))
class AuditFinding(BaseModel): code:str; severity:str; scope:str; evidence:dict; remediation:str; check_version:str='1'
class DataAuditReport(BaseModel): dataset_fingerprint:str; findings:list[AuditFinding]
def _is_id_candidate(name: str) -> bool:
 """Recognize explicit identifier tokens, not arbitrary names ending in ``id``."""
 normalized=name.strip().lower()
 return normalized=="id" or normalized.endswith("_id")
def inspect_dataset(frame:pd.DataFrame,*,source_artifact_sha256:str)->DatasetProfile:
 columns=[]; ids=[]
 for name in frame.columns:
  s=frame[name]; kind='numeric' if pd.api.types.is_numeric_dtype(s) else 'categorical'
  if _is_id_candidate(str(name)): kind='id'; ids.append(name)
  categories=sorted(map(str,s.dropna().unique())) if kind=='categorical' and s.nunique(dropna=True)<=20 else None
  columns.append(FeatureSpec(name=str(name),semantic_type=kind,dtype=str(s.dtype),nullable=bool(s.isna().any()),categories=categories))
 payload=json.dumps([(c.name,c.dtype,c.semantic_type) for c in columns])+source_artifact_sha256
 return DatasetProfile(columns=columns,row_count=len(frame),source_artifact_sha256=source_artifact_sha256,fingerprint=hashlib.sha256(payload.encode()).hexdigest(),id_candidates=ids)
def build_dataset_contract(profile:DatasetProfile,*,target:str|None,task:Literal['regression','binary_classification','multiclass_classification'],id_columns:list[str]|None=None,source_format:Literal['csv','xlsx']='csv')->DatasetContract:
 if not target: raise DatasetConfirmationError('Target requires explicit confirmation.')
 names={x.name for x in profile.columns}
 if target not in names: raise DatasetConfirmationError(f'Target column is absent: {target}')
 ids=id_columns or []; features=[x.name for x in profile.columns if x.name not in {target,*ids} and x.semantic_type!='id']
 return DatasetContract(dataset_fingerprint=profile.fingerprint,source_artifact_sha256=profile.source_artifact_sha256,target=target,task=task,feature_columns=features,id_columns=ids,source_format=source_format)
def run_data_audit(contract:DatasetContract,frame:pd.DataFrame)->DataAuditReport:
 findings=[]
 if frame.duplicated().any(): findings.append(AuditFinding(code='DUPLICATE_ROWS',severity='warning',scope='dataset',evidence={'count':int(frame.duplicated().sum())},remediation='Review duplicate records before protocol freeze.'))
 for name in frame.columns:
  s=frame[name]
  if s.isna().any(): findings.append(AuditFinding(code='MISSING_VALUES',severity='warning',scope='feature',evidence={'column':name,'count':int(s.isna().sum())},remediation='Create a versioned missing-data transformation.'))
  if s.nunique(dropna=True)<=1: findings.append(AuditFinding(code='CONSTANT_COLUMN',severity='warning',scope='feature',evidence={'column':name},remediation='Exclude or justify this non-informative feature.'))
 return DataAuditReport(dataset_fingerprint=contract.dataset_fingerprint,findings=sorted(findings,key=lambda x:(x.code,str(x.evidence))))
def _persist_json(root:Path,name:str,value:BaseModel)->None:
 destination=root/name; fd,temp=tempfile.mkstemp(prefix=".dataset-",dir=root)
 try:
  with os.fdopen(fd,"w",encoding="utf-8") as handle: handle.write(value.model_dump_json(indent=2)); handle.flush(); os.fsync(handle.fileno())
  os.replace(temp,destination)
 finally: Path(temp).unlink(missing_ok=True)

def persist_dataset_contract(project_root:Path,contract:DatasetContract,report:DataAuditReport,profile:DatasetProfile|None=None)->None:
 root=Path(project_root).resolve()/"data"; root.mkdir(parents=True,exist_ok=True)
 _persist_json(root,"dataset-contract.json",contract)
 _persist_json(root,"data-audit.json",report)
 if profile is not None: _persist_json(root,"dataset-profile.json",profile)

def persist_dataset_bytes(project_root:Path,data:bytes,*,original_name:str="dataset.csv",media_type:str="text/csv")->ArtifactRef:
 return ArtifactStore(project_root).ingest_bytes(data,metadata=ArtifactMetadata(media_type=media_type,source_kind="upload",original_name=original_name))

def load_dataset_contract(project_root:Path)->DatasetContract:
 return DatasetContract.model_validate_json((Path(project_root)/"data"/"dataset-contract.json").read_text(encoding="utf-8"))

def load_dataset_profile(project_root:Path)->DatasetProfile:
 return DatasetProfile.model_validate_json((Path(project_root)/"data"/"dataset-profile.json").read_text(encoding="utf-8"))

def load_data_audit(project_root:Path)->DataAuditReport:
 return DataAuditReport.model_validate_json((Path(project_root)/"data"/"data-audit.json").read_text(encoding="utf-8"))

def load_dataset_frame(project_root:Path)->pd.DataFrame:
 contract=load_dataset_contract(project_root)
 with ArtifactStore(project_root).open(ArtifactRef(sha256=contract.source_artifact_sha256)) as handle:
  return pd.read_excel(handle) if contract.source_format=='xlsx' else pd.read_csv(handle)
