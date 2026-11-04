"""Local API contract checks with a fake persistence layer, never production."""
import os
import sys
import types
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

core = types.ModuleType('core')
core.DB_BACKEND = 'postgres'
core.db = types.SimpleNamespace(dsn='isolated-mock-only')
spec = importlib.util.spec_from_file_location('_sampe_auth_test', Path(__file__).resolve().parents[1] / 'auth.py')
auth = importlib.util.module_from_spec(spec)
with patch.dict(sys.modules, {'core': core}):
    spec.loader.exec_module(auth)


class FakeAccess:
    challenges = set()
    sessions = []

    def __init__(self, dsn):
        assert dsn == 'isolated-mock-only'

    def new_google_challenge(self, nonce):
        self.challenges.add(nonce)

    def start_google_session(self, sub, email, name, picture, nonce, session_token):
        if nonce not in self.challenges:
            raise PermissionError('consumed')
        self.challenges.remove(nonce)
        self.sessions.append((sub, email, session_token))


class GoogleDirectApiTests(unittest.TestCase):
    def setUp(self):
        FakeAccess.challenges.clear()
        FakeAccess.sessions.clear()
        self.env = patch.dict(os.environ, {'GOOGLE_DIRECT_AUTH_ENABLED': 'true',
            'GOOGLE_CLIENT_ID': 'client.example', 'GOOGLE_AUTH_ALLOWED_ORIGINS': 'https://sampe.test'})
        self.env.start()
        self.access = patch('postgres.access.PostgresAccess', FakeAccess)
        self.access.start()
        self.app = FastAPI()
        self.app.include_router(auth.router)
        self.client = TestClient(self.app, base_url='https://sampe.test')
        self.headers = {'Origin': 'https://sampe.test'}

    def tearDown(self):
        self.client.close()
        self.access.stop()
        self.env.stop()

    def test_nonce_session_and_replay(self):
        challenge = self.client.post('/api/auth/google-direct/challenge', headers=self.headers)
        self.assertEqual(challenge.status_code, 200)
        nonce = challenge.json()['nonce']
        claims = {'sub':'stable-sub', 'email':'buyer@gmail.com', 'email_verified':True, 'nonce':nonce}
        with patch('google_direct.verify_google_id_token', return_value=claims):
            response = self.client.post('/api/auth/google-direct', headers=self.headers, json={'credential':'test'})
            self.assertEqual(response.status_code, 200)
            self.assertIn('HttpOnly', response.headers['set-cookie'])
            self.assertEqual(len(FakeAccess.sessions), 1)
            self.client.cookies.set('sampe_google_nonce', nonce, path='/api/auth/google-direct')
            self.assertEqual(self.client.post('/api/auth/google-direct', headers=self.headers, json={'credential':'test'}).status_code, 403)

    def test_rejects_wrong_origin_and_nonce(self):
        self.assertEqual(self.client.post('/api/auth/google-direct/challenge', headers={'Origin':'https://evil.example'}).status_code, 403)
        self.client.post('/api/auth/google-direct/challenge', headers=self.headers)
        claims = {'sub':'s','email':'a@gmail.com','email_verified':True,'nonce':'wrong'}
        with patch('google_direct.verify_google_id_token', return_value=claims):
            self.assertEqual(self.client.post('/api/auth/google-direct', headers=self.headers, json={'credential':'test'}).status_code, 401)
        self.assertEqual(FakeAccess.sessions, [])

    def test_rejects_third_party_email_without_google_authority(self):
        nonce = self.client.post('/api/auth/google-direct/challenge', headers=self.headers).json()['nonce']
        claims = {'sub':'s','email':'a@thirdparty.example','email_verified':True,'nonce':nonce}
        with patch('google_direct.verify_google_id_token', return_value=claims):
            result = self.client.post('/api/auth/google-direct', headers=self.headers, json={'credential':'test'})
        self.assertEqual(result.status_code, 403)
        self.assertEqual(FakeAccess.sessions, [])


if __name__ == '__main__':
    unittest.main()
