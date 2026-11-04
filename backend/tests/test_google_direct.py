"""Google token validation with generated keys; never calls Google or production."""
import os
import time
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from google.auth import crypt, jwt

import google_direct


class GoogleTokenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        private = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                    serialization.NoEncryption())
        cls.public = key.public_key().public_bytes(serialization.Encoding.PEM,
                                                   serialization.PublicFormat.SubjectPublicKeyInfo).decode()
        cls.signer = crypt.RSASigner.from_string(private, key_id='test-key')

    def token(self, **override):
        payload = {'iss': 'https://accounts.google.com', 'aud': 'client.example', 'sub': 'stable-sub',
                   'email': 'owner@gmail.com', 'email_verified': True, 'iat': int(time.time()),
                   'exp': int(time.time()) + 300}
        payload.update(override)
        return jwt.encode(self.signer, payload).decode()

    def verify(self, token, cert=None):
        class Response:
            status = 200
            data = ('{"test-key": ' + __import__('json').dumps(cert or self.public) + '}').encode()
        with patch('google.auth.transport.requests.Request', return_value=lambda *a, **kw: Response()):
            return google_direct.verify_google_id_token(token, 'client.example')

    def test_valid_and_invalid_token_properties(self):
        self.assertEqual(self.verify(self.token())['sub'], 'stable-sub')
        for token in (self.token(aud='wrong'), self.token(exp=int(time.time()) - 600),
                      self.token(iss='https://wrong.example'), self.token(email_verified=False)):
            with self.assertRaises(ValueError):
                self.verify(token)
        other = rsa.generate_private_key(public_exponent=65537, key_size=2048).public_key()
        other_pem = other.public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()
        with self.assertRaises(ValueError):
            self.verify(self.token(), cert=other_pem)

    def test_email_authority_and_origin(self):
        self.assertEqual(google_direct.authoritative_identity({'sub':'s','email':'a@work.example','email_verified':True,'hd':'work.example'})[0], 's')
        with self.assertRaises(PermissionError):
            google_direct.authoritative_identity({'sub':'s','email':'a@thirdparty.example','email_verified':True})
        with patch.dict(os.environ, {'GOOGLE_AUTH_ALLOWED_ORIGINS':'https://sampe.web.id,http://localhost:3000'}):
            self.assertTrue(google_direct.allowed_origin('https://sampe.web.id'))
            self.assertFalse(google_direct.allowed_origin('https://attacker.example'))


if __name__ == '__main__':
    unittest.main()
