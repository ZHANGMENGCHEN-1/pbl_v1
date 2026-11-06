from test_library import client,unlock_first,cfg,B,H


def test_reset_switch_is_explicit_and_off_by_default(client,monkeypatch):
    monkeypatch.delenv('LIBRARY_RESET_ON_REFRESH',raising=False)
    assert client.get(B).json()['testing_reset_on_refresh'] is False
    assert client.post(B+'/testing/reset-progress',headers=H).status_code==403
    assert client.post(B+'/testing/reset-progress').status_code==400


def test_reset_clears_only_current_library_session_progress(client,monkeypatch):
    monkeypatch.setenv('LIBRARY_RESET_ON_REFRESH','true')
    unlock_first(client)
    before_config=cfg(client,0)
    analyses=client.get(B+'/activities/group_books/analyses',headers=H).json()
    body={'strategy':'read_first','check':'evidence','reason':None,'phase':'before','base_version':0}
    client.post(B+'/activities/group_books/plan-card',headers=H,json=body)
    client.put(B+'/activities/group_books/draft',headers=H,json={'payload':{'plan':'unfinished draft'}})
    other={'X-Session-ID':'other-reset-browser-session'}
    client.post(B+'/activities/group_books/plan-card',headers=other,json=body)
    other_before=client.get(B+'/learning',headers=other).json()
    astro=client.get('/api/projects/astronomy-lab/config',headers=H).json()
    assert client.get(B).json()['testing_reset_on_refresh'] is True
    assert client.post(B+'/testing/reset-progress',headers=H).status_code==200
    fresh=client.get(B+'/learning',headers=H).json()
    assert fresh['completed']==0 and fresh['plan_card'] is None
    assert [a['status'] for a in fresh['activities']]==['available','locked','locked','locked']
    assert fresh['activities'][0]['plan'] is None and fresh['activities'][0]['draft']=={}
    assert client.get(B+'/plan-history',headers=H).json()==[]
    assert cfg(client,0)==before_config
    assert analyses
    assert client.get(B+'/activities/group_books/analyses',headers=H).json()==[]
    assert client.get(B+'/runs?activity_id=group_books',headers=H).json()==[]
    assert client.get(B+'/learning',headers=other).json()==other_before
    assert client.get('/api/projects/astronomy-lab/config',headers=H).json()==astro
    assert client.post(B+'/testing/reset-progress',headers=H).status_code==200
