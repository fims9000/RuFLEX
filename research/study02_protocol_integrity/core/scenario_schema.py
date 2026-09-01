from __future__ import annotations
from dataclasses import dataclass
@dataclass(frozen=True)
class Scenario:
 scenario_id:str; pair_id:str; generator_family:str; seed:int; clean_or_corrupt:str; violation_family:str|None; stage:str|None; severity:str|None; state:dict
 def validate(self):
  if self.clean_or_corrupt not in {'clean','corrupt'}: raise ValueError('invalid scenario role')
  if (self.clean_or_corrupt=='clean') != (self.violation_family is None): raise ValueError('clean/corruption invariant')
  if self.clean_or_corrupt=='corrupt' and not self.violation_family: raise ValueError('missing planted violation')
