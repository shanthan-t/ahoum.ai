import os
import django
from django.conf import settings
from django.test.utils import get_runner

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ahoum.settings")
django.setup()

import unittest
from accounts.tests import AuthTests

class DebugTest(AuthTests):
    def test_debug(self):
        from unittest import mock
        from django.contrib.auth.hashers import check_password
        from accounts.models import EmailOTP
        
        with mock.patch("accounts.services._generate_otp_code", return_value="123456"):
            self.client.post(self.signup_url, self.valid_payload)
            
            otp_obj = EmailOTP.objects.first()
            print(f"OTP HASH: {otp_obj.otp_hash}")
            print(f"CHECK 123456: {check_password('123456', otp_obj.otp_hash)}")
            print(f"CHECK 000000: {check_password('000000', otp_obj.otp_hash)}")

            res = self.client.post(self.verify_url, {
                "email": self.valid_payload["email"],
                "otp": "000000"
            })
            print(f"STATUS: {res.status_code}")
            print(f"DATA: {res.data}")
            self.assertEqual(res.status_code, 400)

TestRunner = get_runner(settings)
test_runner = TestRunner(verbosity=2)
test_runner.run_tests(["__main__.DebugTest"])
