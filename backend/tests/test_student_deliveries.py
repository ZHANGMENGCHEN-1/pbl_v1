from test_library import client,unlock_first,B,H


def test_first_delivery_requires_students_answers_and_keeps_them(client):
    result=unlock_first(client)
    payload={'plan':'根据实验填写自己的分组与中心结果。','analysis_id':result['analysis_id']}
    url=B+'/activities/group_books/submit'
    assert client.post(url,headers=H,json={'payload':payload}).status_code==422
    payload['student_result']={'counts':[2,3],'centers':[4,16]}
    response=client.post(url,headers=H,json={'payload':payload})
    assert response.status_code==200,response.text
    saved=response.json()['activities'][0]['submission']['payload']
    # Completion is checked, but student mistakes must not be silently replaced.
    assert saved['student_result']==payload['student_result']
    assert saved['tool_result']['counts']==[3,2]
    assert saved['tool_result']['centers']!=[4,16]
    reloaded=client.get(B+'/learning',headers=H).json()['activities'][0]['submission']['payload']
    assert reloaded['student_result']==payload['student_result']
    payload['student_result']['counts']=[2,2]
    assert client.post(url,headers=H,json={'payload':payload}).status_code==422
    payload['student_result']={'counts':[2,3],'centers':[None,16]}
    assert client.post(url,headers=H,json={'payload':payload}).status_code==422
