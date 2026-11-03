import io
import json
import os
import unittest
from app import app

class TestReelsStudioPro(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        self.client = app.test_client()

    def test_index_route(self):
        res = self.client.get('/')
        self.assertEqual(res.status_code, 200)
        html = res.data.decode('utf-8')

        # Check key form inputs and elements are present
        self.assertIn('id="rawBotInput"', html)
        self.assertIn('id="dishName"', html)
        self.assertIn('id="voiceText"', html)
        self.assertIn('id="sub0"', html)
        self.assertIn('id="sub1"', html)
        self.assertIn('id="sub2"', html)
        self.assertIn('id="sub3"', html)
        self.assertIn('id="sub4"', html)
        self.assertIn('id="customAudioInput"', html)
        self.assertIn('id="fullPostKit"', html)
        self.assertIn('id="sceneSlotsGrid"', html)
        self.assertIn('id="statusBox"', html)
        self.assertIn('id="generateBtn"', html)
        self.assertIn('id="resultCard"', html)
        self.assertIn('id="resultPlayer"', html)
        self.assertIn('id="downloadLink"', html)
        self.assertIn('id="downloadPostKit"', html)
        self.assertIn('parseBotResponse()', html)
        self.assertIn('startGeneration()', html)
        self.assertIn('style.css', html)
        self.assertIn('app.js', html)

        # Check speed adjustment elements
        self.assertIn('id="videoSpeedSlider"', html)
        self.assertIn('id="speedValue"', html)
        self.assertIn('id="downloadSpeedBtn"', html)
        self.assertIn('id="btnSpeedVal"', html)
        self.assertIn('min="0.75"', html)
        self.assertIn('max="1.75"', html)
        self.assertIn('step="0.25"', html)
        self.assertIn('value="1.0"', html)

        # Check 4 neural voices selector
        self.assertIn('id="voiceSpeakerSelect"', html)
        self.assertIn('ru-RU-DmitryNeural', html)
        self.assertIn('ru-RU-SvetlanaNeural', html)
        self.assertIn('ru-RU-DenisNeural', html)
        self.assertIn('ru-RU-DariyaNeural', html)

        # Check background music module
        self.assertIn('id="bgMusicToggle"', html)
        self.assertIn('id="bgMusicSelect"', html)
        self.assertIn('id="uploadMusicBtn"', html)
        self.assertIn('id="musicFileInput"', html)
        self.assertIn('id="bgMusicVolume"', html)
        self.assertIn('id="bgMusicVolumeVal"', html)

    def test_static_assets(self):
        css_res = self.client.get('/static/css/style.css')
        self.assertEqual(css_res.status_code, 200)
        css = css_res.data.decode('utf-8')
        self.assertIn('#0e1117', css)
        self.assertIn('#ff6b35', css)
        self.assertIn('speed-control-panel', css)
        self.assertIn('videoSpeedSlider', css)
        self.assertIn('music-module-card', css)
        self.assertIn('toggle-switch', css)
        self.assertIn('btn-music-upload', css)

        js_res = self.client.get('/static/js/app.js')
        self.assertEqual(js_res.status_code, 200)
        js = js_res.data.decode('utf-8')
        self.assertIn('parseBotResponse', js)
        self.assertIn('showToast', js)
        self.assertIn('startGeneration', js)
        self.assertIn('sceneSlots', js)
        self.assertIn('setupSpeedControlListeners', js)
        self.assertIn('/export_speed', js)
        self.assertIn('loadMusicList', js)
        self.assertIn('setupMusicModule', js)
        self.assertIn('setupVoiceSpeakerListener', js)

    def test_get_music_list(self):
        res = self.client.get('/get_music_list')
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertEqual(data['status'], 'ok')
        self.assertIsInstance(data['tracks'], list)
        self.assertGreaterEqual(len(data['tracks']), 3)

        filenames = [t['filename'] for t in data['tracks']]
        self.assertIn('01_lofi_kitchen.mp3', filenames)
        self.assertIn('02_acoustic_cozy.mp3', filenames)
        self.assertIn('03_modern_lounge.mp3', filenames)

    def test_upload_music_invalid(self):
        # Empty upload
        res = self.client.post('/upload_music', data={})
        self.assertEqual(res.status_code, 400)

        # Invalid file format (e.g. .txt)
        data = {
            'file': (io.BytesIO(b'not an audio file'), 'test.txt')
        }
        res2 = self.client.post('/upload_music', data=data, content_type='multipart/form-data')
        self.assertEqual(res2.status_code, 400)

    def test_upload_music_valid(self):
        # Valid mp3 file upload
        data = {
            'file': (io.BytesIO(b'ID3\x03\x00\x00\x00\x00\x00#dummy_mp3_header_bytes'), 'custom_test_track.mp3')
        }
        res = self.client.post('/upload_music', data=data, content_type='multipart/form-data')
        self.assertEqual(res.status_code, 200)
        resp_data = json.loads(res.data)
        self.assertEqual(resp_data['status'], 'ok')
        self.assertIn('custom_test_track', resp_data['filename'])

        # Clean up test file
        test_file_path = os.path.join('static', 'audio', 'music', resp_data['filename'])
        if os.path.exists(test_file_path):
            try: os.remove(test_file_path)
            except OSError: pass

    def test_render_reel_missing_files(self):
        res = self.client.post('/render_reel', data={})
        self.assertEqual(res.status_code, 400)
        data = json.loads(res.data)
        self.assertEqual(data['status'], 'error')
        self.assertIn('Кадры не загружены', data['message'])

    def test_export_speed_invalid_values(self):
        # Speed out of range (< 0.5 or > 2.0)
        res = self.client.post('/export_speed', 
                               data=json.dumps({'speed': 0.1}),
                               content_type='application/json')
        self.assertEqual(res.status_code, 400)
        data = json.loads(res.data)
        self.assertEqual(data['status'], 'error')

        res2 = self.client.post('/export_speed', 
                                data=json.dumps({'speed': 3.5}),
                                content_type='application/json')
        self.assertEqual(res2.status_code, 400)

    def test_export_speed_valid_processing(self):
        # Test export_speed on web_outputs/latest_reel.mp4 if present
        if os.path.exists(os.path.join("web_outputs", "latest_reel.mp4")):
            res = self.client.post('/export_speed',
                                   data=json.dumps({'speed': 1.25}),
                                   content_type='application/json')
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.headers.get('Content-Type'), 'video/mp4')
            disposition = res.headers.get('Content-Disposition', '')
            self.assertTrue('kitartchef_1.25x.mp4' in disposition or 'kitartchef_speed.mp4' in disposition)
            self.assertTrue(len(res.data) > 1000)

if __name__ == '__main__':
    unittest.main()
