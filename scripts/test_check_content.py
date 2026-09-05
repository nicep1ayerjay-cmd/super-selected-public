#!/usr/bin/env python3
from __future__ import annotations

import unittest

from scripts.check_content import banned_phrases


class BannedPhrasesTest(unittest.TestCase):
    def test_customer_is_normal_public_wording(self) -> None:
        self.assertEqual(banned_phrases("为客户提供专业服务。"), [])

    def test_internal_engineering_wording_is_still_blocked(self) -> None:
        self.assertEqual(banned_phrases("这是内部工程的部署流程。"), ["内部工程", "部署流程"])


if __name__ == "__main__":
    unittest.main()
