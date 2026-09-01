from __future__ import annotations
import hashlib,json
def canonical_hash(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def semantic_pair_diff(clean:dict,corrupt:dict,expected_family:str)->dict:
 shared={k:clean[k] for k in clean if k in corrupt and clean[k]==corrupt[k]}
 changed={k:{'clean':clean.get(k),'corrupt':corrupt.get(k)} for k in set(clean)|set(corrupt) if clean.get(k)!=corrupt.get(k)}
 if set(changed)!={'protocol_mutation'}: raise ValueError(f'unexpected pair differences: {sorted(changed)}')
 mutation=corrupt['protocol_mutation']
 if mutation.get('family')!=expected_family: raise ValueError('wrong primary violation')
 return {'pair_base_hash':canonical_hash(shared),'clean_spec_hash':canonical_hash(clean),'corrupt_spec_hash':canonical_hash(corrupt),'primary_family':expected_family,'changed':changed}
