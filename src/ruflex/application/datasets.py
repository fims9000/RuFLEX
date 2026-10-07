from __future__ import annotations
import hashlib, json, os, tempfile
from pathlib import Path
from typing import Literal
import pandas as pd
from pydantic import BaseModel, Field
from sklearn.model_selection import GroupShuffleSplit
from uuid import UUID, uuid4
from ruflex.application.artifacts import ArtifactMetadata, ArtifactRef, ArtifactStore
ROW_IDENTITY_SCHEME = "dataset-fingerprint/source-row/v1"


def row_identity(dataset_fingerprint: str, source_row: int) -> str:
 """Stable typed identity for one materialized row in one DatasetContract."""
 if source_row < 0: raise DatasetConfirmationError("Source row must be non-negative.")
 payload=f"{ROW_IDENTITY_SCHEME}|{dataset_fingerprint}|{source_row}".encode()
 return f"row:{hashlib.sha256(payload).hexdigest()}"
class DatasetConfirmationError(ValueError): pass
class FeatureSpec(BaseModel): name:str; semantic_type:str; dtype:str; nullable:bool; categories:list[str]|None=None; proposed_role:Literal['feature','id_candidate']='feature'; role_confidence:float=Field(default=.5,ge=0.,le=1.); role_reason:str='No identifier token was detected.'
class DatasetProfile(BaseModel): columns:list[FeatureSpec]; row_count:int; source_artifact_sha256:str; fingerprint:str; id_candidates:list[str]
class SchemaComparison(BaseModel): compatible:bool; missing_columns:list[str]; unexpected_columns:list[str]
class DatasetContract(BaseModel):
 dataset_fingerprint:str; source_artifact_sha256:str; target:str; task:Literal['regression','binary_classification','multiclass_classification']; feature_columns:list[str]; id_columns:list[str]=Field(default_factory=list); excluded_columns:list[str]=Field(default_factory=list); source_format:Literal['csv','xlsx']='csv'; row_identity_scheme:str=ROW_IDENTITY_SCHEME; role_decisions:dict[str,Literal['target','feature','id','excluded']]=Field(default_factory=dict)
 def compare_schema(self,frame:pd.DataFrame):
  expected=set(self.feature_columns)|set(self.id_columns)|set(self.excluded_columns)|{self.target}; actual=set(frame.columns); return SchemaComparison(compatible=expected==actual,missing_columns=sorted(expected-actual),unexpected_columns=sorted(actual-expected))
class SplitContract(BaseModel):
 """Immutable, dataset-bound membership contract for a scientific split.

 ``role_source_rows`` is the source of truth.  Training receives those exact
 rows rather than re-running a random splitter, so reopen/final-test replay
 cannot silently change group membership.
 """
 schema_version:int=1
 split_id:UUID=Field(default_factory=uuid4)
 dataset_fingerprint:str
 dataset_artifact_sha256:str
 family:Literal['RANDOM','GROUP','TEMPORAL','SITE_HOLDOUT','DEVICE_HOLDOUT','SPATIAL','REGIME']
 split_seed:int
 validation_fraction:float=Field(gt=0.,lt=1.)
 test_fraction:float=Field(ge=0.,lt=1.)
 group_column:str|None=None
 time_column:str|None=None
 site_column:str|None=None
 device_column:str|None=None
 spatial_column:str|None=None
 regime_column:str|None=None
 role_source_rows:dict[Literal['train','validation','test'],list[int]]
 role_identity_hashes:dict[Literal['train','validation','test'],str]
 split_identity:str
 scientific_note:str=(
  'This contract records exact source-row membership. It makes the declared split family auditable; it does not establish external validity by itself.'
 )

 def role_rows(self, role:str)->tuple[int,...]: return tuple(self.role_source_rows[role])
class TransformStepContract(BaseModel):
 step_type:Literal['MedianImputer','StandardScaler','MinMaxScaler','OneHotEncoder','OrdinalEncoder','FeatureSelector','CustomTrustedTransform']
 parameters:dict
 fit_role:Literal['TRAIN']='TRAIN'
 input_columns:list[str]
 output_columns:list[str]
 artifact_identity:str|None=None
 version:str='1'
class TransformPipelineContract(BaseModel):
 schema_version:int=1
 pipeline_id:UUID=Field(default_factory=uuid4)
 dataset_fingerprint:str
 split_contract_id:str|None=None
 feature_order:list[str]
 steps:list[TransformStepContract]
 preprocessing_artifact_sha256:str
 fit_role:Literal['TRAIN']='TRAIN'
 pipeline_identity:str
 scientific_note:str='Transforms are fitted only on TRAIN rows. This provenance boundary does not independently detect every possible data leak.'
class LeakageAuditReport(BaseModel):
 schema_version:int=1
 audit_id:UUID=Field(default_factory=uuid4)
 dataset_fingerprint:str
 rigor_profile:Literal['EXPLORATORY','CONFIRMATORY','HIGH_ASSURANCE_LIKE']='CONFIRMATORY'
 split_contract_id:str|None=None
 transform_pipeline_id:str|None=None
 status:Literal['PASS','WARN','FAIL']
 findings:list['AuditFinding']=Field(default_factory=list)
 scientific_note:str='This audit verifies declared provenance invariants. It does not prove absence of every semantic or deployment-specific leakage path.'
class RigorProfileContract(BaseModel):
 profile:Literal['EXPLORATORY','CONFIRMATORY','HIGH_ASSURANCE_LIKE']
 required_evidence:list[str]
 stop_rules:list[str]
 scientific_note:str='A rigor profile declares required evidence and stop rules. It is not a truth, safety, certification, or generalization label.'
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
  is_id=_is_id_candidate(str(name))
  if is_id: kind='id'; ids.append(name)
  categories=sorted(map(str,s.dropna().unique())) if kind=='categorical' and s.nunique(dropna=True)<=20 else None
  columns.append(FeatureSpec(name=str(name),semantic_type=kind,dtype=str(s.dtype),nullable=bool(s.isna().any()),categories=categories,proposed_role='id_candidate' if is_id else 'feature',role_confidence=.95 if is_id else .85,role_reason='Explicit identifier token: exact id or _id suffix.' if is_id else 'No explicit identifier token; retain as a feature candidate pending DatasetContract confirmation.'))
 payload=json.dumps([(c.name,c.dtype,c.semantic_type) for c in columns])+source_artifact_sha256
 return DatasetProfile(columns=columns,row_count=len(frame),source_artifact_sha256=source_artifact_sha256,fingerprint=hashlib.sha256(payload.encode()).hexdigest(),id_candidates=ids)
def build_dataset_contract(profile:DatasetProfile,*,target:str|None,task:Literal['regression','binary_classification','multiclass_classification'],id_columns:list[str]|None=None,excluded_columns:list[str]|None=None,source_format:Literal['csv','xlsx']='csv')->DatasetContract:
 if not target: raise DatasetConfirmationError('Target requires explicit confirmation.')
 names=[column.name for column in profile.columns]
 if len(names)!=len(set(names)): raise DatasetConfirmationError('Dataset columns must be unique before roles can be confirmed.')
 if target not in names: raise DatasetConfirmationError(f'Target column is absent: {target}')
 ids=id_columns or []
 if len(ids)!=len(set(ids)): raise DatasetConfirmationError('ID columns must be unique; remove duplicate column names.')
 unknown_ids=sorted(set(ids)-set(names))
 if unknown_ids: raise DatasetConfirmationError(f'ID columns are absent from the dataset: {", ".join(unknown_ids)}')
 if target in ids: raise DatasetConfirmationError('The target column cannot also be declared as an ID column.')
 excluded=excluded_columns or []
 if len(excluded)!=len(set(excluded)): raise DatasetConfirmationError('Excluded columns must be unique; remove duplicate column names.')
 unknown_excluded=sorted(set(excluded)-set(names))
 if unknown_excluded: raise DatasetConfirmationError(f'Excluded columns are absent from the dataset: {", ".join(unknown_excluded)}')
 if target in excluded: raise DatasetConfirmationError('The target column cannot also be excluded from model features.')
 overlap=sorted(set(ids)&set(excluded))
 if overlap: raise DatasetConfirmationError(f'ID and excluded feature roles must not overlap: {", ".join(overlap)}')
 features=[name for name in names if name not in {target,*ids,*excluded}]
 if not features: raise DatasetConfirmationError('At least one model feature must remain after excluding columns.')
 decisions={name:('target' if name==target else 'id' if name in ids else 'excluded' if name in excluded else 'feature') for name in names}
 return DatasetContract(dataset_fingerprint=profile.fingerprint,source_artifact_sha256=profile.source_artifact_sha256,target=target,task=task,feature_columns=features,id_columns=ids,excluded_columns=excluded,source_format=source_format,role_decisions=decisions)
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

def _split_root(project_root:Path)->Path:
 root=Path(project_root).resolve()/"data"/"splits"; root.mkdir(parents=True,exist_ok=True); return root

def _rows_hash(dataset_fingerprint:str, rows:list[int])->str:
 payload={"dataset_fingerprint":dataset_fingerprint,"source_rows":sorted(int(row) for row in rows)}
 return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(",",":" )).encode()).hexdigest()

def _split_identity(contract:DatasetContract, *, family:str, split_seed:int, identity_column:str|None, role_rows:dict[str,list[int]])->str:
 payload={"dataset_fingerprint":contract.dataset_fingerprint,"family":family,"split_seed":split_seed,"identity_column":identity_column,"roles":{key:sorted(value) for key,value in sorted(role_rows.items())}}
 return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(",",":" )).encode()).hexdigest()

def _validate_role_rows(rows:dict[str,list[int]])->None:
 expected={"train","validation","test"}
 if set(rows)!=expected: raise DatasetConfirmationError("Split roles must be exactly train, validation and test.")
 sets={role:set(values) for role,values in rows.items()}
 if any(len(values)!=len(sets[role]) for role,values in rows.items()): raise DatasetConfirmationError("Split contract contains duplicate source rows.")
 if sets["train"] & sets["validation"] or sets["train"] & sets["test"] or sets["validation"] & sets["test"]: raise DatasetConfirmationError("Split contract roles must be disjoint.")
 if not sets["train"] or not sets["validation"]: raise DatasetConfirmationError("Split contract requires non-empty TRAIN and VALIDATION roles.")

def create_split_contract(project_root:Path, *, family:Literal['RANDOM','GROUP','TEMPORAL','SITE_HOLDOUT','DEVICE_HOLDOUT','SPATIAL','REGIME'], split_seed:int, validation_fraction:float=.2, test_fraction:float=.2, group_column:str|None=None, time_column:str|None=None, site_column:str|None=None, device_column:str|None=None, spatial_column:str|None=None, regime_column:str|None=None)->SplitContract:
 """Materialize a declared split before fitting, with exact persisted rows.

 Every executable family records its exact source rows. Identity holdouts use
 group-disjoint membership; TEMPORAL uses an ordered holdout rather than a
 random approximation.
 """
 contract=load_dataset_contract(project_root); frame=load_dataset_frame(project_root)
 if validation_fraction<=0 or test_fraction<0 or validation_fraction+test_fraction>=1: raise DatasetConfirmationError("Split fractions must be positive/valid and sum to less than one.")
 eligible=frame.loc[frame[contract.target].notna()].copy()
 if eligible.empty: raise DatasetConfirmationError("No target-labelled rows are available for a split contract.")
 source_rows=[int(row) for row in eligible.index]
 identity_columns={'GROUP':group_column,'SITE_HOLDOUT':site_column,'DEVICE_HOLDOUT':device_column,'SPATIAL':spatial_column,'REGIME':regime_column}
 identity_column=identity_columns.get(family)
 if family in identity_columns:
  if not identity_column or identity_column not in frame.columns: raise DatasetConfirmationError("GROUP split requires an existing group column." if family=='GROUP' else f"{family} split requires its declared identity column.")
  if eligible[identity_column].isna().any(): raise DatasetConfirmationError(f"{family} split cannot assign rows with missing identity.")
  groups=eligible[identity_column].astype(str).to_numpy()
  if len(set(groups))<3: raise DatasetConfirmationError("GROUP split requires at least three distinct groups.")
  outer=GroupShuffleSplit(n_splits=1,test_size=test_fraction,random_state=int(split_seed))
  remaining_positions,test_positions=next(outer.split(eligible,groups=groups))
  remaining=eligible.iloc[remaining_positions]; remaining_groups=groups[remaining_positions]
  effective_validation=validation_fraction/(1.-test_fraction)
  inner=GroupShuffleSplit(n_splits=1,test_size=effective_validation,random_state=int(split_seed)+1)
  train_positions,validation_positions=next(inner.split(remaining,groups=remaining_groups))
  role_rows={"train":[int(row) for row in remaining.iloc[train_positions].index],"validation":[int(row) for row in remaining.iloc[validation_positions].index],"test":[int(row) for row in eligible.iloc[test_positions].index]}
  group_sets={role:set(frame.loc[indices,identity_column].astype(str)) for role,indices in role_rows.items()}
  if group_sets['train']&group_sets['validation'] or group_sets['train']&group_sets['test'] or group_sets['validation']&group_sets['test']: raise DatasetConfirmationError(f"{family} split generation produced overlapping identities.")
 elif family=='TEMPORAL':
  if not time_column or time_column not in frame.columns: raise DatasetConfirmationError("TEMPORAL split requires a declared time column.")
  if eligible[time_column].isna().any(): raise DatasetConfirmationError("TEMPORAL split cannot assign rows with missing time.")
  ordered=eligible.assign(__source_row=eligible.index).sort_values([time_column,'__source_row'],kind='stable')
  test_count=round(len(ordered)*test_fraction); validation_count=round(len(ordered)*validation_fraction)
  role_rows={'train':[int(row) for row in ordered.iloc[:len(ordered)-test_count-validation_count].index],'validation':[int(row) for row in ordered.iloc[len(ordered)-test_count-validation_count:len(ordered)-test_count].index],'test':[int(row) for row in ordered.iloc[len(ordered)-test_count:].index]}
  role_times={role:frame.loc[rows,time_column] for role,rows in role_rows.items()}
  if not (role_times['train'].max() < role_times['validation'].min() and role_times['validation'].max() < role_times['test'].min()):
   raise DatasetConfirmationError('TEMPORAL split requires strict forward role boundaries with no shared boundary timestamp.')
 else:
  # This is deterministic and preserves legacy RANDOM semantics without
  # exposing future family declarations as random fallbacks.
  import numpy as np
  generator=np.random.default_rng(int(split_seed)); shuffled=np.asarray(source_rows,dtype=int); generator.shuffle(shuffled)
  test_count=round(len(shuffled)*test_fraction); validation_count=round(len(shuffled)*validation_fraction)
  role_rows={"test":sorted(int(row) for row in shuffled[:test_count]),"validation":sorted(int(row) for row in shuffled[test_count:test_count+validation_count]),"train":sorted(int(row) for row in shuffled[test_count+validation_count:])}
 _validate_role_rows(role_rows)
 hashes={role:_rows_hash(contract.dataset_fingerprint,rows) for role,rows in role_rows.items()}
 result=SplitContract(dataset_fingerprint=contract.dataset_fingerprint,dataset_artifact_sha256=contract.source_artifact_sha256,family=family,split_seed=int(split_seed),validation_fraction=validation_fraction,test_fraction=test_fraction,group_column=group_column,time_column=time_column,site_column=site_column,device_column=device_column,spatial_column=spatial_column,regime_column=regime_column,role_source_rows={role:sorted(rows) for role,rows in role_rows.items()},role_identity_hashes=hashes,split_identity=_split_identity(contract,family=family,split_seed=int(split_seed),identity_column=(time_column if family=='TEMPORAL' else identity_column),role_rows=role_rows))
 _persist_json(_split_root(project_root),f"{result.split_id}.json",result)
 _atomic_split_pointer(Path(project_root).resolve()/"data"/"active-split-contract.json",result)
 return result

def _atomic_split_pointer(path:Path,contract:SplitContract)->None:
 path.parent.mkdir(parents=True,exist_ok=True)
 fd,temp=tempfile.mkstemp(prefix='.split-',dir=path.parent)
 try:
  with os.fdopen(fd,'w',encoding='utf-8') as handle: handle.write(json.dumps({"split_id":str(contract.split_id),"split_identity":contract.split_identity},sort_keys=True)); handle.flush(); os.fsync(handle.fileno())
  os.replace(temp,path)
 finally: Path(temp).unlink(missing_ok=True)

def load_split_contract(project_root:Path,split_id:UUID|str|None=None)->SplitContract:
 if split_id is None:
  pointer=json.loads((Path(project_root).resolve()/"data"/"active-split-contract.json").read_text(encoding='utf-8')); split_id=pointer['split_id']
 path=_split_root(project_root)/f"{split_id}.json"; result=SplitContract.model_validate_json(path.read_text(encoding='utf-8'))
 contract=load_dataset_contract(project_root)
 if result.dataset_fingerprint!=contract.dataset_fingerprint or result.dataset_artifact_sha256!=contract.source_artifact_sha256: raise DatasetConfirmationError("Split contract does not belong to the active DatasetContract revision.")
 _validate_role_rows(result.role_source_rows)
 if any(result.role_identity_hashes[role]!=_rows_hash(contract.dataset_fingerprint,result.role_source_rows[role]) for role in ('train','validation','test')): raise DatasetConfirmationError("Split contract role identity hashes are malformed.")
 return result

def list_split_contracts(project_root:Path)->list[SplitContract]:
 contracts=[]
 for path in _split_root(project_root).glob('*.json'):
  try: contracts.append(load_split_contract(project_root,path.stem))
  except (OSError,ValueError,DatasetConfirmationError) as error: raise DatasetConfirmationError(f'Persisted SplitContract {path.name} is malformed or incompatible: {error}') from error
 return sorted(contracts,key=lambda item:str(item.split_id))

def _transform_root(project_root:Path)->Path:
 root=Path(project_root).resolve()/"data"/"transforms"; root.mkdir(parents=True,exist_ok=True); return root

def create_transform_pipeline_contract(project_root:Path, *, contract:DatasetContract, split, preprocessing_artifact_sha256:str, split_contract_id:str|None=None)->TransformPipelineContract:
 """Persist the exact train-only numerical and categorical preprocessing."""
 normalization=split.normalization.to_dict(); columns=list(split.feature_columns)
 steps=[]
 if split.numeric_feature_columns:
  steps.append(TransformStepContract(step_type='MedianImputer',parameters={'values':{column:split.imputation_values[column] for column in split.numeric_feature_columns},'missing_value_policy':'median'},input_columns=list(split.numeric_feature_columns),output_columns=list(split.numeric_feature_columns),artifact_identity=preprocessing_artifact_sha256))
 if split.categorical_feature_columns:
  steps.append(TransformStepContract(step_type='OrdinalEncoder',parameters={'categories':split.categorical_encoders,'missing_values':{column:split.imputation_values[column] for column in split.categorical_feature_columns},'unknown_value':-1.0,'missing_value_policy':'train_mode'},input_columns=list(split.categorical_feature_columns),output_columns=list(split.categorical_feature_columns),artifact_identity=preprocessing_artifact_sha256))
 if normalization['mode']=='standard': steps.append(TransformStepContract(step_type='StandardScaler',parameters={'center':normalization['center'],'scale':normalization['scale']},input_columns=columns,output_columns=columns,artifact_identity=preprocessing_artifact_sha256))
 elif normalization['mode']=='minmax': steps.append(TransformStepContract(step_type='MinMaxScaler',parameters={'minimum':normalization['minimum'],'maximum':normalization['maximum']},input_columns=columns,output_columns=columns,artifact_identity=preprocessing_artifact_sha256))
 payload={'dataset_fingerprint':contract.dataset_fingerprint,'split_contract_id':split_contract_id,'feature_order':columns,'steps':[item.model_dump(mode='json') for item in steps],'preprocessing_artifact_sha256':preprocessing_artifact_sha256}
 identity='transform-pipeline:'+hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()
 result=TransformPipelineContract(**payload,pipeline_identity=identity)
 _persist_json(_transform_root(project_root),f'{result.pipeline_id}.json',result)
 return result

def _transform_pipeline_identity(result:TransformPipelineContract)->str:
 payload={
  'dataset_fingerprint':result.dataset_fingerprint,
  'split_contract_id':result.split_contract_id,
  'feature_order':result.feature_order,
  'steps':[item.model_dump(mode='json') for item in result.steps],
  'preprocessing_artifact_sha256':result.preprocessing_artifact_sha256,
 }
 return 'transform-pipeline:'+hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def load_transform_pipeline_contract(project_root:Path,pipeline_id:UUID|str)->TransformPipelineContract:
 result=TransformPipelineContract.model_validate_json((_transform_root(project_root)/f'{pipeline_id}.json').read_text(encoding='utf-8'))
 contract=load_dataset_contract(project_root)
 if result.dataset_fingerprint!=contract.dataset_fingerprint: raise DatasetConfirmationError('Transform pipeline does not belong to the active DatasetContract revision.')
 if result.fit_role!='TRAIN' or any(step.fit_role!='TRAIN' for step in result.steps): raise DatasetConfirmationError('Transform pipeline has a non-TRAIN fitting scope.')
 if result.pipeline_identity!=_transform_pipeline_identity(result): raise DatasetConfirmationError('Transform pipeline identity does not match its persisted provenance.')
 if result.split_contract_id is not None: load_split_contract(project_root,result.split_contract_id)
 return result

def list_transform_pipeline_contracts(project_root:Path)->list[TransformPipelineContract]:
 pipelines=[]
 for path in _transform_root(project_root).glob('*.json'):
  try: pipelines.append(load_transform_pipeline_contract(project_root,path.stem))
  except (OSError,ValueError,DatasetConfirmationError) as error: raise DatasetConfirmationError(f'Persisted TransformPipelineContract {path.name} is malformed or incompatible: {error}') from error
 return sorted(pipelines,key=lambda item:str(item.pipeline_id))

def _leakage_root(project_root:Path)->Path:
 root=Path(project_root).resolve()/'data'/'leakage-audits'; root.mkdir(parents=True,exist_ok=True); return root

def rigor_profile_contract(profile:Literal['EXPLORATORY','CONFIRMATORY','HIGH_ASSURANCE_LIKE'])->RigorProfileContract:
 requirements={
  'EXPLORATORY':(['DatasetContract','TrainingRun','ValidationEvaluation'],['Do not present validation selection as final-test evidence.']),
  'CONFIRMATORY':(['DatasetContract','SplitContract','TransformPipelineContract','TrainingRun','ValidationEvaluation','DecisionThresholdPolicy','SelectivePredictionPolicy','FinalTestEvaluation','Lineage','VerificationBundle'],['Block final test until validation-derived policies are frozen.','Block policy fitting after the first final-test access.']),
  'HIGH_ASSURANCE_LIKE':(['DatasetContract','SplitContract','TransformPipelineContract','DataLeakageAudit','GeneralizationContract','BehaviorSpec','ExplanationCheck','AssuranceCase','VerificationBundle'],['Block on failed provenance or leakage-audit evidence.','Require independent human sign-off outside this software boundary.']),
 }
 required,stops=requirements[profile]; return RigorProfileContract(profile=profile,required_evidence=required,stop_rules=stops)

def run_leakage_audit(project_root:Path, *, split_contract_id:str|None, transform_pipeline_id:str, rigor_profile:Literal['EXPLORATORY','CONFIRMATORY','HIGH_ASSURANCE_LIKE']='CONFIRMATORY')->LeakageAuditReport:
 """Fail closed on structural data-leakage signals before a fitted model is persisted."""
 contract=load_dataset_contract(project_root); findings:list[AuditFinding]=[]
 if contract.target in contract.feature_columns: findings.append(AuditFinding(code='TARGET_IN_FEATURES',severity='fail',scope='dataset',evidence={'target':contract.target},remediation='Remove the target from model feature columns.'))
 pipeline=load_transform_pipeline_contract(project_root,transform_pipeline_id)
 if pipeline.feature_order!=contract.feature_columns: findings.append(AuditFinding(code='FEATURE_ORDER_MISMATCH',severity='fail',scope='transform',evidence={},remediation='Rebuild a transform pipeline for the active DatasetContract.'))
 if pipeline.fit_role!='TRAIN' or any(step.fit_role!='TRAIN' for step in pipeline.steps): findings.append(AuditFinding(code='NON_TRAIN_TRANSFORM_FIT',severity='fail',scope='transform',evidence={},remediation='Fit all preprocessing steps on TRAIN only.'))
 if pipeline.split_contract_id!=split_contract_id: findings.append(AuditFinding(code='SPLIT_PIPELINE_BINDING_MISMATCH',severity='fail',scope='provenance',evidence={},remediation='Bind the transform pipeline to the same immutable split contract.'))
 frame=load_dataset_frame(project_root)
 numeric_target=pd.to_numeric(frame[contract.target],errors='coerce')
 for feature in contract.feature_columns:
  numeric_feature=pd.to_numeric(frame[feature],errors='coerce')
  valid=numeric_feature.notna() & numeric_target.notna()
  if valid.any() and (numeric_feature[valid].equals(numeric_target[valid]) or numeric_feature[valid].equals(1.0-numeric_target[valid])):
   findings.append(AuditFinding(code='TARGET_DERIVED_FEATURE',severity='warning',scope='feature',evidence={'feature':feature,'relationship':'exact_target_or_binary_complement'},remediation='Remove, justify, or explicitly document this target-derived feature before confirmatory use.'))
 feature_columns=list(contract.feature_columns)
 labelled_frame=frame.loc[frame[contract.target].notna(),feature_columns+[contract.target]]
 if feature_columns:
  target_cardinality=labelled_frame.groupby(feature_columns,dropna=False,sort=False)[contract.target].nunique(dropna=True)
  conflicting_vectors=target_cardinality[target_cardinality>1]
  if not conflicting_vectors.empty:
   conflicting_rows=int(labelled_frame.set_index(feature_columns).index.isin(conflicting_vectors.index).sum())
   findings.append(AuditFinding(code='NEAR_DUPLICATE_ROWS',severity='warning',scope='dataset',evidence={'count':conflicting_rows,'conflicting_feature_vectors':int(len(conflicting_vectors)),'method':'exact_feature_vector_duplicate_with_multiple_targets'},remediation='Inspect duplicate or conflicting entity records before interpreting validation results.'))
 if split_contract_id is not None:
  split=load_split_contract(project_root,split_contract_id)
  if split.family=='GROUP' and not split.group_column: findings.append(AuditFinding(code='GROUP_IDENTITY_MISSING',severity='fail',scope='split',evidence={},remediation='Declare the group identity used by the GROUP split.'))
  identity_column={'GROUP':split.group_column,'SITE_HOLDOUT':split.site_column,'DEVICE_HOLDOUT':split.device_column,'SPATIAL':split.spatial_column,'REGIME':split.regime_column}.get(split.family)
  if identity_column:
   identities={role:set(frame.loc[rows,identity_column].astype(str)) for role,rows in split.role_source_rows.items()}
   overlap=(identities['train']&identities['validation']) | (identities['train']&identities['test']) | (identities['validation']&identities['test'])
   if overlap: findings.append(AuditFinding(code='DUPLICATE_ENTITY_ACROSS_SPLITS',severity='fail',scope='split',evidence={'identity_column':identity_column,'count':len(overlap)},remediation='Regenerate a disjoint identity holdout split.'))
  if split.family=='TEMPORAL':
   values={role:frame.loc[rows,split.time_column] for role,rows in split.role_source_rows.items()}
   if not (values['train'].max() < values['validation'].min() and values['validation'].max() < values['test'].min()): findings.append(AuditFinding(code='TEMPORAL_LEAKAGE',severity='fail',scope='split',evidence={'time_column':split.time_column},remediation='Use strict forward holdout roles with no boundary-time overlap.'))
 findings.extend(run_data_audit(contract,frame).findings)
 status='FAIL' if any(item.severity=='fail' for item in findings) else ('WARN' if findings else 'PASS')
 result=LeakageAuditReport(dataset_fingerprint=contract.dataset_fingerprint,rigor_profile=rigor_profile,split_contract_id=split_contract_id,transform_pipeline_id=transform_pipeline_id,status=status,findings=findings)
 _persist_json(_leakage_root(project_root),f'{result.audit_id}.json',result); return result

def load_leakage_audit(project_root:Path,audit_id:UUID|str)->LeakageAuditReport:
 result=LeakageAuditReport.model_validate_json((_leakage_root(project_root)/f'{audit_id}.json').read_text(encoding='utf-8'))
 if result.dataset_fingerprint!=load_dataset_contract(project_root).dataset_fingerprint: raise DatasetConfirmationError('Leakage audit does not belong to the active DatasetContract revision.')
 if result.transform_pipeline_id: load_transform_pipeline_contract(project_root,result.transform_pipeline_id)
 if result.split_contract_id: load_split_contract(project_root,result.split_contract_id)
 return result

def list_leakage_audits(project_root:Path)->list[LeakageAuditReport]:
 audits=[]
 for path in _leakage_root(project_root).glob('*.json'):
  try: audits.append(load_leakage_audit(project_root,path.stem))
  except (OSError,ValueError,DatasetConfirmationError) as error: raise DatasetConfirmationError(f'Persisted LeakageAuditReport {path.name} is malformed or incompatible: {error}') from error
 return sorted(audits,key=lambda item:str(item.audit_id))

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
