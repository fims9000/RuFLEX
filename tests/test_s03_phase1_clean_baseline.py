from research.s03_explanation_validation.sample_selection import select_validation_samples

def test_s03_sample_fallback_is_frozen_and_fail_closed():
    rows=[{"source_row":i,"truth":0,"prediction":0} for i in range(10)]
    assert [row["source_row"] for row in select_validation_samples(rows)]==list(range(8))
    try: select_validation_samples(rows[:7])
    except ValueError as error: assert str(error)=="VALIDATION_SUPPORT_LT_8"
    else: raise AssertionError("selection must fail closed below eight rows")
