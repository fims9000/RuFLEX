import pytest
from research.study02_protocol_integrity.scripts.locked_executor import run,LockedExecutionForbidden
from research.study02_protocol_integrity.core.pair_diff import semantic_pair_diff
def test_locked_executor_refuses_before_authorization(tmp_path,monkeypatch):
 monkeypatch.setattr('research.study02_protocol_integrity.scripts.locked_executor.AUTHORIZATION',tmp_path/'missing.json')
 with pytest.raises(LockedExecutionForbidden): run()
def test_semantic_pair_diff_rejects_unrelated_mutation():
 with pytest.raises(ValueError): semantic_pair_diff({'x':1},{'x':2,'protocol_mutation':{'family':'V01'}},'V01')
