import pytest
from blindspot.final_report import panel_metrics


def test_missing_responses_are_visible_and_not_counted_as_correct_verdicts():
    rows=[dict(status='ok',control=False,valid=False,confidence=.9,cost_usd=.1,completion_tokens=10),
          dict(status='ok',control=True,valid=True,confidence=.8,cost_usd=.1,completion_tokens=20),
          dict(status='ok',control=False,valid=True,confidence=.7,cost_usd=.1,completion_tokens=30),
          dict(status='error',control=True,valid=None,finish_reason='length',cost_usd=.1,completion_tokens=40)]
    m=panel_metrics(rows)
    assert m['correct_completed']==2 and m['incorrect_completed']==1 and m['no_usable_verdicts']==1
    assert m['completion_rate']==.75 and m['unusable_reasons']=={'length':1}
    assert m['hit_rate']==.5 and m['false_alarm_rate']==0
    assert m['main_cost_usd']==pytest.approx(.4) and m['median_completion_tokens']==25
    assert m['incorrect_pass_confidence']['mean']==.7
