import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException, Response

from src import app as server


class TeacherAuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.account_file = Path(self.temp_directory.name) / "teachers.json"
        salt = b"test-salt-for-admin"
        password_hash = hashlib.pbkdf2_hmac(
            "sha256",
            b"correct horse battery staple",
            salt,
            server.PASSWORD_HASH_ITERATIONS,
        ).hex()
        self.account_file.write_text(
            json.dumps(
                {
                    "teacher": {
                        "salt": salt.hex(),
                        "password_hash": password_hash,
                    }
                }
            ),
            encoding="utf-8",
        )
        self.file_patcher = patch.object(server, "TEACHERS_FILE", self.account_file)
        self.file_patcher.start()

    def tearDown(self):
        self.file_patcher.stop()
        self.temp_directory.cleanup()

    def test_mutation_routes_require_teacher_dependency(self):
        routes = {
            route.path: route
            for route in server.app.routes
            if route.path in {
                "/activities/{activity_name}/signup",
                "/activities/{activity_name}/unregister",
            }
        }
        self.assertEqual(
            set(routes),
            {
                "/activities/{activity_name}/signup",
                "/activities/{activity_name}/unregister",
            },
        )
        for route in routes.values():
            self.assertTrue(
                any(
                    dependency.call is server.require_teacher
                    for dependency in route.dependant.dependencies
                )
            )

    def test_anonymous_users_are_rejected_by_teacher_dependency(self):
        with self.assertRaises(HTTPException) as exception:
            server.require_teacher(None)
        self.assertEqual(exception.exception.status_code, 401)

    def test_teacher_can_manage_registrations_and_sign_out(self):
        response = Response()
        result = server.login(
            server.LoginRequest(
                username="teacher",
                password="correct horse battery staple",
            ),
            response,
        )
        session_cookie = response.headers["set-cookie"]
        session_id = session_cookie.split(";", maxsplit=1)[0].split("=", maxsplit=1)[1]
        self.assertTrue(result["authenticated"])
        self.assertEqual(server.require_teacher(session_id), "teacher")

        participants_before = list(server.activities["Chess Club"]["participants"])
        email = "new-student@mergington.edu"
        signup_result = server.signup_for_activity(
            "Chess Club", email, _="teacher"
        )
        unregister_result = server.unregister_from_activity(
            "Chess Club", email, _="teacher"
        )
        self.assertIn(email, signup_result["message"])
        self.assertIn(email, unregister_result["message"])
        self.assertEqual(
            server.activities["Chess Club"]["participants"],
            participants_before,
        )
        server.logout(Response(), session_id)
        with self.assertRaises(HTTPException):
            server.require_teacher(session_id)

    def test_invalid_password_is_rejected(self):
        with self.assertRaises(HTTPException) as exception:
            server.login(
                server.LoginRequest(username="teacher", password="incorrect"),
                Response(),
            )
        self.assertEqual(exception.exception.status_code, 401)

    def test_missing_account_file_disables_sign_in_with_clear_error(self):
        self.account_file.unlink()

        with self.assertRaises(HTTPException) as exception:
            server.login(
                server.LoginRequest(
                    username="teacher",
                    password="correct horse battery staple",
                ),
                Response(),
            )
        self.assertEqual(exception.exception.status_code, 503)
        self.assertEqual(
            exception.exception.detail,
            "Teacher login is not configured",
        )


if __name__ == "__main__":
    unittest.main()
