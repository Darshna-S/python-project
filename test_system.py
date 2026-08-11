import unittest
import sqlite3
import time
from app import app
from scoring import calculate_complete_score, calculate_weighted_score

class TestEProjectSystem(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app.testing = True

    def test_sqlite3_row_scoring_fix(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("CREATE TABLE EventLog (event_type TEXT)")
        c.execute("INSERT INTO EventLog VALUES ('Face Not Detected')")
        c.execute("INSERT INTO EventLog VALUES ('Browser Focus Lost')")
        conn.commit()

        rows = c.execute("SELECT event_type FROM EventLog").fetchall()
        conn.close()

        res = calculate_weighted_score(rows)
        self.assertEqual(res["penalty"], 15)
        self.assertEqual(res["score"], 85)
        self.assertEqual(res["risk_label"], "Low Risk")

    def test_homepage_buttons(self):
        with self.app.test_client() as client:
            res = client.get('/')
            self.assertEqual(res.status_code, 200)
            self.assertIn(b'Candidate Login', res.data)
            self.assertIn(b'Admin Login', res.data)

    def test_event_logs_table_route(self):
        with self.app.test_client() as client:
            res = client.get('/event_logs')
            self.assertEqual(res.status_code, 200)
            self.assertIn(b'Chronological Event Logs Table', res.data)

    def test_candidate_registration_photo(self):
        ts = int(time.time())
        with self.app.test_client() as client:
            res = client.post('/register', data={
                'candidate_id': f'CAND_REG_{ts}',
                'name': f'Candidate Registration {ts}',
                'email': f'cand_{ts}@example.com',
                'password': 'pass123_test'
            }, follow_redirects=True)
            self.assertEqual(res.status_code, 200)
            self.assertIn(b'Registration successful', res.data)

    def test_end_session_metrics(self):
        with self.app.test_client() as client:
            ts = int(time.time())
            c_id = f'CAND_END_{ts}'
            client.post('/register', data={
                'candidate_id': c_id,
                'name': 'End Session Test',
                'email': f'end_{ts}@example.com',
                'password': 'pass'
            })
            with client.session_transaction() as sess:
                sess['candidate_id'] = c_id
            client.get('/update_session/start')
            res_end = client.get('/update_session/end', follow_redirects=True)
            self.assertEqual(res_end.status_code, 200)
            self.assertIn(b'Session Summary', res_end.data)

    def test_candidate_cannot_access_admin(self):
        with self.app.test_client() as client:
            with client.session_transaction() as sess:
                sess['candidate_id'] = 'CAND_TEST_101'
                sess['name'] = 'Test Candidate'

            res = client.get('/admin', follow_redirects=True)
            self.assertIn(b'Access Denied', res.data)

if __name__ == '__main__':
    unittest.main()
