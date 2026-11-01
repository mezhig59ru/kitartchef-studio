import json
import pytest
from app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_index_route(client):
    res = client.get('/')
    assert res.status_code == 200
    html = res.data.decode('utf-8')
    # Check key form inputs and elements are present
    assert 'id="rawBotInput"' in html
    assert 'id="dishName"' in html
    assert 'id="voiceText"' in html
    assert 'id="sub0"' in html
    assert 'id="sub1"' in html
    assert 'id="sub2"' in html
    assert 'id="sub3"' in html
    assert 'id="sub4"' in html
    assert 'id="customAudioInput"' in html
    assert 'id="fullPostKit"' in html
    assert 'id="sceneSlotsGrid"' in html
    assert 'id="statusBox"' in html
    assert 'id="generateBtn"' in html
    assert 'id="resultCard"' in html
    assert 'id="resultPlayer"' in html
    assert 'id="downloadLink"' in html
    assert 'id="downloadPostKit"' in html
    assert 'parseBotResponse()' in html
    assert 'startGeneration()' in html
    assert 'style.css' in html
    assert 'app.js' in html

def test_static_assets(client):
    css_res = client.get('/static/css/style.css')
    assert css_res.status_code == 200
    assert '#0e1117' in css_res.data.decode('utf-8')
    assert '#ff6b35' in css_res.data.decode('utf-8')

    js_res = client.get('/static/js/app.js')
    assert js_res.status_code == 200
    assert 'parseBotResponse' in js_res.data.decode('utf-8')
    assert 'showToast' in js_res.data.decode('utf-8')
    assert 'startGeneration' in js_res.data.decode('utf-8')
    assert 'sceneSlots' in js_res.data.decode('utf-8')

def test_render_reel_missing_files(client):
    res = client.post('/render_reel', data={})
    assert res.status_code == 400
    data = json.loads(res.data)
    assert data['status'] == 'error'
    assert 'Кадры не загружены' in data['message']
