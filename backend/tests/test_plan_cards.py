from test_library import client, B, H, unlock_first, cfg


def post(client,activity='group_books',**changes):
    body={'strategy':'read_first','check':'evidence','reason':None,'phase':'before','base_version':0,**changes}
    return client.post(B+f'/activities/{activity}/plan-card',headers=H,json=body)


def test_initial_plan_requires_two_valid_choices_without_scoring(client):
    assert client.get(B+'/learning',headers=H).json()['plan_card'] is None
    assert post(client,strategy='').status_code==422
    assert post(client,check='random-typing').status_code==422
    assert post(client,reason='different_task').status_code==422
    response=post(client)
    assert response.status_code==200,response.text
    state=response.json();card=state['plan_card']
    assert state['completed']==0 and state['activities'][1]['status']=='locked'
    assert card['version']==1 and card['kind']=='initial' and card['phase']=='before'
    assert card['changed_fields']==[] and card['reason'] is None
    assert 'score' not in card
    assert client.get(B+'/learning',headers=H).json()['plan_card']==card
    assert '我的做法' in state['activities'][0]['plan']['text']


def test_plan_inheritance_revision_reason_history_and_conflict(client):
    assert post(client).status_code==200
    unlock_first(client)
    assert client.get(B+'/learning',headers=H).json()['plan_card']['strategy']=='read_first'
    response=post(client,'explain_algorithm',base_version=1)
    assert response.status_code==200,response.text
    card=response.json()['plan_card']
    assert card['version']==2 and card['previous_version']==1
    assert card['kind']=='carried_forward' and card['reason'] is None
    assert post(client,'explain_algorithm',base_version=2,strategy='try_first',phase='during').status_code==422
    response=post(client,'explain_algorithm',base_version=2,strategy='try_first',reason='found_problem',phase='during')
    assert response.status_code==200,response.text
    card=response.json()['plan_card']
    assert card['changed_fields']==['strategy'] and card['phase']=='during' and card['kind']=='modified'
    assert card['check']=='evidence' and card['reason']=='found_problem'
    assert post(client,'explain_algorithm',base_version=2).status_code==409
    history=client.get(B+'/plan-history',headers=H).json()
    assert [p['version'] for p in history]==[3,2,1]
    assert history[-1]['strategy']=='read_first' and history[0]['strategy']=='try_first'
    assert all(p['submitted_at'] and p['question_version']==1 for p in history)
    assert response.json()['completed']==1


def test_legacy_text_is_not_guessed_and_sessions_are_isolated(client):
    unlock_first(client)
    assert client.get(B+'/learning',headers=H).json()['plan_card'] is None
    assert post(client,'explore_2d').status_code==403
    old=client.get(B+'/learning',headers=H).json()['activities'][0]['plan']['text']
    archived=post(client).json()['plan_card']
    assert archived['legacy_plan_text']==old
    assert post(client,'explain_algorithm',base_version=1).status_code==200
    other={'X-Session-ID':'other-plan-card-session-123'}
    assert client.get(B+'/learning',headers=other).json()['plan_card'] is None
    assert client.get(B+'/plan-history',headers=other).json()==[]
    assert client.get(B+'/plan-history').status_code==400
    # Existing project config and astronomy storage remain independent.
    assert cfg(client,1)['config']['system_prompt']
    assert client.get('/api/projects/astronomy-lab/activities',headers=H).json()==[]
