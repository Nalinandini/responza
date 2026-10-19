import unittest
from unittest.mock import MagicMock, patch
import os
import database
import app
from app import app as flask_app, emergency_data, validate_coordinates

class ResponzaTestCase(unittest.TestCase):
    def setUp(self):
        flask_app.config['TESTING'] = True
        self.client = flask_app.test_client()

    def test_routes_splash_and_home(self):
        # 1. Test / is strictly splash
        res_splash = self.client.get('/')
        self.assertEqual(res_splash.status_code, 200)
        self.assertIn(b'Responza', res_splash.data)
        self.assertIn(b'/home', res_splash.data)

        # POST to / should not be allowed
        res_post_root = self.client.post('/')
        self.assertEqual(res_post_root.status_code, 405)

        # 2. Test /home GET
        res_home = self.client.get('/home')
        self.assertEqual(res_home.status_code, 200)
        self.assertIn(b'Chest Pain', res_home.data)

        # 3. Test /home POST language selection
        res_home_te = self.client.post('/home', data={'language': 'te'})
        self.assertEqual(res_home_te.status_code, 200)
        self.assertIn('గుండె పోటు'.encode('utf-8'), res_home_te.data)

        res_home_hi = self.client.post('/home', data={'language': 'hi'})
        self.assertEqual(res_home_hi.status_code, 200)
        self.assertIn('सीने में दर्द'.encode('utf-8'), res_home_hi.data)

    def test_coordinate_validation(self):
        # Valid coords
        lat, lon, url = validate_coordinates("17.385044", "78.486671")
        self.assertEqual(lat, 17.385044)
        self.assertEqual(lon, 78.486671)
        self.assertIn("maps.google.com", url)

        # Out of bounds coords
        lat_bad, lon_bad, url_bad = validate_coordinates("195.0", "78.486671")
        self.assertIsNone(lat_bad)
        self.assertIsNone(lon_bad)
        self.assertEqual(url_bad, "Location unavailable.")

        # Non-numeric coords
        lat_str, lon_str, url_str = validate_coordinates("invalid_lat", "invalid_lon")
        self.assertIsNone(lat_str)
        self.assertIsNone(lon_str)
        self.assertEqual(url_str, "Location unavailable.")

        # Empty coords
        lat_emp, lon_emp, url_emp = validate_coordinates("", "")
        self.assertIsNone(lat_emp)
        self.assertIsNone(lon_emp)
        self.assertEqual(url_emp, "Location unavailable.")

    def test_handle_emergency(self):
        res = self.client.post('/handle_emergency', data={
            'language': 'en',
            'emergency': 'Chest Pain'
        })
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Loosen tight clothing.', res.data)
        self.assertIn(b'tel:108', res.data)
        self.assertIn(b'GPS Location Status', res.data)

        # Invalid emergency should redirect safely to /home
        res_invalid = self.client.post('/handle_emergency', data={
            'language': 'en',
            'emergency': 'NonExistentEmergency'
        })
        self.assertEqual(res_invalid.status_code, 302)
        self.assertIn('/home', res_invalid.headers['Location'])

    def test_send_sms_graceful_error_handling(self):
        # When Twilio client fails or credentials fail
        with patch.object(app, 'twilio_client') as mock_client:
            mock_client.messages.create.side_effect = Exception("Twilio API Connection Failed")
            
            res = self.client.post('/send_sms', data={
                'language': 'en',
                'emergency': 'Fire',
                'latitude': '17.385044',
                'longitude': '78.486671'
            })
            self.assertEqual(res.status_code, 200)
            # Must NOT expose raw exception message in HTML output
            self.assertNotIn(b'Twilio API Connection Failed', res.data)
            # Must show user-friendly fallback
            self.assertIn(b'Unable to Dispatch Automatic SMS', res.data)
            self.assertIn(b'tel:101', res.data)  # Direct call link for Fire

            # Verify incident was persisted in SQLite as FAILED
            incidents = database.get_incidents(limit=5)
            self.assertGreater(len(incidents), 0)
            latest = incidents[0]
            self.assertEqual(latest['emergency_type'], 'Fire')
            self.assertEqual(latest['status'], 'FAILED')
            self.assertIn('****', latest['recipient_masked'])

    def test_send_sms_success_mock(self):
        # Test successful alert dispatch
        with patch.object(app, 'twilio_client') as mock_client:
            mock_message = MagicMock()
            mock_message.sid = "SM_TEST_MOCK_SID_12345"
            mock_client.messages.create.return_value = mock_message

            res = self.client.post('/send_sms', data={
                'language': 'en',
                'emergency': 'Road Accident',
                'latitude': '17.385044',
                'longitude': '78.486671'
            })
            self.assertEqual(res.status_code, 200)
            self.assertIn(b'Dispatched Successfully', res.data)

            # Check database persistence
            incidents = database.get_incidents(limit=5)
            latest = incidents[0]
            self.assertEqual(latest['emergency_type'], 'Road Accident')
            self.assertEqual(latest['status'], 'SUCCESS')
            self.assertEqual(latest['twilio_sid'], 'SM_TEST_MOCK_SID_12345')

    def test_incident_history(self):
        res = self.client.get('/history')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Incident Log & Alert History', res.data)
        self.assertIn(b'Privacy Protection Active', res.data)

    def test_credentials_not_hardcoded(self):
        with open('app.py', 'r', encoding='utf-8') as f:
            content = f.read()
        self.assertNotIn("FAKE_AUTH_TOKEN", content)
        self.assertNotIn("FAKE_ACCOUNT_SID", content)       
        self.assertIn("os.environ.get('TWILIO_ACCOUNT_SID')", content)
        self.assertIn("os.environ.get('TWILIO_AUTH_TOKEN')", content)

if __name__ == '__main__':
    unittest.main()
