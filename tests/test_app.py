"""Unified Test Suite Entry Point.

This module aggregates the modular domain test suites:
- test_auth: Authentication, registration, and session tests
- test_student: Student submission, validation, and form participation tests
- test_faculty: Faculty analytics, custom forms, and anonymity guarantees
- test_admin: Admin management, reporting, and CSV export tests
- test_security: Role access boundaries, redirects, and route security tests
"""

import sys
from pathlib import Path

# Ensure workspace root is in sys.path for direct script execution
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import unittest

from tests.test_admin import AdminTests
from tests.test_auth import AuthTests
from tests.test_faculty import FacultyTests
from tests.test_security import SecurityTests
from tests.test_student import StudentTests


def suite():
    test_suite = unittest.TestSuite()
    for test_class in (AuthTests, StudentTests, FacultyTests, AdminTests, SecurityTests):
        tests = unittest.defaultTestLoader.loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)
    return test_suite


if __name__ == "__main__":
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite())
