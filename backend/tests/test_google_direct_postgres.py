"""Google identity acceptance, restricted to the disposable local test database."""
import concurrent.futures
import os
import secrets
import unittest
from unittest.mock import patch
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from postgres.access import PostgresAccess

DSN = os.environ.get('SAMPE_POSTGRES_DSN', '')
target = urlparse(DSN)
class GooglePostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if (os.environ.get('SAMPE_POSTGRES_ENV') != 'testing' or target.hostname != '127.0.0.1'
                or target.port != 55435 or target.path != '/sampe_google_test'):
            raise unittest.SkipTest('Requires the dedicated disposable local Google auth database')

    def setUp(self):
        self.db = PostgresAccess(DSN)
        self.tag = secrets.token_hex(8)
        self.email = f'{self.tag}@gmail.com'
        self.user = 'user-' + self.tag
        self.license = 'license-' + self.tag
        self.now = datetime.now(timezone.utc)
        with self.db.connect() as conn:
            conn.execute('INSERT INTO sampe.members (user_id,email,created_at) VALUES (%s,%s,%s)',
                         (self.user, self.email, self.now))
            conn.execute("INSERT INTO sampe.licenses (id,label,email,source,duration_days,created_at,owner_user_id) VALUES (%s,'test',%s,'test',30,%s,%s)",
                         (self.license, self.email, self.now, self.user))

    def login(self, sub, email=None, nonce=None):
        nonce = nonce or secrets.token_urlsafe(32)
        self.db.new_google_challenge(nonce)
        token = secrets.token_urlsafe(32)
        user = self.db.start_google_session(sub, email or self.email, 'test', None, nonce, token)
        return user, token, nonce

    def test_existing_member_and_license_stay_owned_and_logout(self):
        user, token, nonce = self.login('sub-' + self.tag)
        self.assertEqual(user, self.user)
        self.assertEqual(self.db.member_for_session(token)['user_id'], self.user)
        self.assertEqual(self.db.license_for_member(user)['id'], self.license)
        with self.assertRaises(PermissionError):
            self.db.start_google_session('sub-' + self.tag, self.email, '', None, nonce, secrets.token_urlsafe(32))
        self.db.end_session(token)
        self.assertIsNone(self.db.member_for_session(token))
        self.assertEqual(self.login('sub-' + self.tag)[0], self.user)

    def test_new_member_and_different_sub_rejected(self):
        sub = 'sub-' + self.tag
        self.assertEqual(self.login(sub)[0], self.user)
        with self.assertRaises(PermissionError):
            self.login('other-' + self.tag)
        with self.assertRaises(PermissionError):
            self.login(sub, 'other-' + self.email)
        new_user = self.login('new-' + self.tag, 'new-' + self.email)[0]
        self.assertNotEqual(new_user, self.user)
        self.assertIsNone(self.db.license_for_member(new_user))

    def test_expired_challenge_and_concurrent_replay(self):
        expired = secrets.token_urlsafe(32)
        self.db.new_google_challenge(expired, self.now - timedelta(minutes=6))
        with self.assertRaises(PermissionError):
            self.db.start_google_session('expired-' + self.tag, self.email, '', None, expired, secrets.token_urlsafe(32))
        nonce = secrets.token_urlsafe(32)
        self.db.new_google_challenge(nonce)
        def attempt():
            try:
                return self.db.start_google_session('race-' + self.tag, self.email, '', None, nonce, secrets.token_urlsafe(32))
            except PermissionError:
                return None
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: attempt(), range(2)))
        self.assertEqual(sum(bool(x) for x in results), 1)

    def test_same_google_sub_racing_across_two_emails(self):
        sub = 'shared-' + self.tag
        pairs = [('a-' + self.email, secrets.token_urlsafe(32)), ('b-' + self.email, secrets.token_urlsafe(32))]
        for _, nonce in pairs:
            self.db.new_google_challenge(nonce)
        def attempt(pair):
            try:
                return self.db.start_google_session(sub, pair[0], '', None, pair[1], secrets.token_urlsafe(32))
            except PermissionError:
                return None
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(attempt, pairs))
        self.assertEqual(sum(bool(x) for x in results), 1)
        with self.db.connect() as conn:
            count = conn.execute('SELECT count(*) AS n FROM sampe.google_identities WHERE google_sub=%s', (sub,)).fetchone()['n']
        self.assertEqual(count, 1)

    def test_me_expired_revoked_and_claim_contract(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        import auth
        from license_rules import license_status

        _, token, _ = self.login('api-' + self.tag)
        with self.db.connect() as conn:
            conn.execute('UPDATE sampe.licenses SET activated_at=%s, expires_at=%s WHERE id=%s',
                         (self.now - timedelta(days=4), self.now - timedelta(days=1), self.license))
        self.assertEqual(license_status(self.db.license_for_member(self.user)), 'expired')
        app = FastAPI()
        app.include_router(auth.router)
        with TestClient(app, base_url='https://sampe.test') as client:
            client.cookies.set('session_token', token)
            response = client.get('/api/auth/me')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['user']['user_id'], self.user)
            self.assertEqual(response.json()['license']['status'], 'expired')
            self.assertFalse(response.json()['writable'])
            with self.db.connect() as conn:
                conn.execute('UPDATE sampe.licenses SET revoked=true WHERE id=%s', (self.license,))
            self.assertEqual(client.get('/api/auth/me').json()['license']['status'], 'revoked')
            self.assertEqual(client.post('/api/auth/claim', json={'code':'not-valid'}).status_code, 404)

    def test_google_login_through_api_preserves_member_and_license(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        import auth
        app = FastAPI()
        app.include_router(auth.router)
        config = {'GOOGLE_DIRECT_AUTH_ENABLED':'true', 'GOOGLE_CLIENT_ID':'test-client',
                  'GOOGLE_AUTH_ALLOWED_ORIGINS':'https://sampe.test'}
        with patch.dict(os.environ, config), TestClient(app, base_url='https://sampe.test') as client:
            headers = {'Origin':'https://sampe.test'}
            nonce = client.post('/api/auth/google-direct/challenge', headers=headers).json()['nonce']
            claims = {'sub':'full-' + self.tag, 'email':self.email, 'email_verified':True, 'nonce':nonce}
            with patch('google_direct.verify_google_id_token', return_value=claims):
                response = client.post('/api/auth/google-direct', headers=headers, json={'credential':'mock-signed-token'})
            self.assertEqual(response.status_code, 200)
            me = client.get('/api/auth/me')
            self.assertEqual(me.status_code, 200)
            self.assertEqual(me.json()['user']['user_id'], self.user)
            self.assertEqual(me.json()['license']['id'], self.license)
            self.assertEqual(client.post('/api/auth/logout').status_code, 200)
            self.assertEqual(client.get('/api/auth/me').status_code, 401)

    def test_claim_valid_license_through_existing_api(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        import auth
        _, token, _ = self.login('claim-' + self.tag)
        code = 'TEST-' + self.tag.upper()
        claim_id = 'claim-' + self.tag
        with self.db.connect() as conn:
            conn.execute("INSERT INTO sampe.licenses (id,code,label,email,source,duration_days,created_at) VALUES (%s,%s,'claim',%s,'test',7,%s)",
                         (claim_id, code, self.email, self.now))
        app = FastAPI()
        app.include_router(auth.router)
        with TestClient(app, base_url='https://sampe.test') as client:
            client.cookies.set('session_token', token)
            response = client.post('/api/auth/claim', json={'code':code})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['id'], claim_id)
        with self.db.connect() as conn:
            self.assertEqual(conn.execute('SELECT owner_user_id FROM sampe.licenses WHERE id=%s', (claim_id,)).fetchone()['owner_user_id'], self.user)


if __name__ == '__main__':
    unittest.main()
