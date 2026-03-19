"""Unit tests for PiiChecker.

Covers:
- AC-09-01: PII（メールアドレス）の検出 — severity=WARNING、details に pii_type 情報
- AC-09-02: detect_pii=False でスキップ — Issue なし
- AC-09-03: PIIなしデータでの無検出 — issues 空
- 電話番号（US/JP）の検出
- 複数PII種別混在
- None値スキップ
- 空データセット
- stats["pii_detected_count"] の検証
- checker_name == "pii" の検証
- severity=WARNING の検証
"""

from __future__ import annotations

import pytest
from datasets import Dataset

from evaldataset.checks.content import PiiChecker
from evaldataset.config import CheckerConfig
from evaldataset.models import Severity


class TestPiiChecker:
    """PiiChecker のユニットテスト。"""

    # --- フィクスチャ ---

    @pytest.fixture
    def config(self) -> CheckerConfig:
        """detect_pii=True のデフォルト CheckerConfig。"""
        return CheckerConfig()

    @pytest.fixture
    def checker(self, config: CheckerConfig) -> PiiChecker:
        """detect_pii=True の PiiChecker インスタンス。"""
        return PiiChecker(config)

    # --- ヘルパー ---

    @staticmethod
    def _make_dataset(texts: list[str | None]) -> Dataset:
        """テスト用 Dataset を作成する。None を含む場合も対応。"""
        return Dataset.from_dict({"text": texts})

    # --- AC-09-01: PII（メールアドレス）の検出 ---

    def test_email_pii_detected(self, checker: PiiChecker) -> None:
        """AC-09-01: メールアドレスを含むテキストで severity=WARNING の Issue が発生する。"""
        texts = ["Contact us at user@example.com for info."]
        dataset = self._make_dataset(texts)
        result = checker.check(dataset, text_field="text")

        warnings = [i for i in result.issues if i.severity == Severity.WARNING]
        assert len(warnings) >= 1, "メールアドレスを含む場合 WARNING が発生するべき"

    def test_email_pii_details_contain_pii_type(self, checker: PiiChecker) -> None:
        """AC-09-01: Issue の details に pii_type 情報が含まれる。"""
        texts = ["Contact us at user@example.com for info."]
        dataset = self._make_dataset(texts)
        result = checker.check(dataset, text_field="text")

        assert result.has_issues, "メールアドレス検出で Issue が発生するべき"
        # details にはPII種別の情報が含まれること（キー名は実装に依存するが情報として存在する）
        for issue in result.issues:
            assert issue.details, "Issue.details は空でないべき"
            # pii_type キーが直接あるか、またはまとめて格納されているか検証する
            has_pii_type_info = (
                "pii_type" in issue.details
                or "pii_types" in issue.details
                or "pii_matches" in issue.details
            )
            assert has_pii_type_info, (
                f"Issue.details に pii_type 情報が含まれるべき: {issue.details}"
            )

    def test_email_pii_details_indicate_email_type(self, checker: PiiChecker) -> None:
        """AC-09-01: details で 'email' というPII種別が識別できる。"""
        texts = ["Reach us at user@example.com anytime."]
        dataset = self._make_dataset(texts)
        result = checker.check(dataset, text_field="text")

        assert result.has_issues, "メールアドレス検出で Issue が発生するべき"

        # details の中で 'email' が識別できることを確認する
        # 実装方式に応じて pii_type 直接指定か pii_types/pii_matches のいずれかで確認
        for issue in result.issues:
            details = issue.details
            found_email = (
                details.get("pii_type") == "email"
                or "email" in details.get("pii_types", {})
                or any(
                    m.get("pii_type") == "email"
                    for m in details.get("pii_matches", [])
                )
            )
            assert found_email, (
                f"details で 'email' PII種別が識別できるべき: {details}"
            )

    def test_email_pii_row_indices(self, checker: PiiChecker) -> None:
        """AC-09-01: row_indices にメールアドレスを含むレコードのインデックスが含まれる。"""
        texts = [
            "Clean text here",
            "Contact user@example.com",
            "Another clean text",
        ]
        dataset = self._make_dataset(texts)
        result = checker.check(dataset, text_field="text")

        assert result.has_issues, "メールアドレス検出で Issue が発生するべき"
        affected_indices = [idx for issue in result.issues for idx in issue.row_indices]
        assert 1 in affected_indices, (
            "メールアドレスを含む index 1 が row_indices に含まれるべき"
        )
        assert 0 not in affected_indices, "PIIなし index 0 は row_indices に含まれないべき"
        assert 2 not in affected_indices, "PIIなし index 2 は row_indices に含まれないべき"

    def test_email_pii_severity_is_warning(self, checker: PiiChecker) -> None:
        """AC-09-01: PII 検出 Issue の severity が WARNING である。"""
        texts = ["Email: user@example.com"]
        dataset = self._make_dataset(texts)
        result = checker.check(dataset, text_field="text")

        assert result.has_issues, "メールアドレス検出で Issue が発生するべき"
        for issue in result.issues:
            assert issue.severity == Severity.WARNING, (
                f"Issue の severity は WARNING であるべき: {issue.severity}"
            )

    # --- AC-09-02: detect_pii=False でスキップ ---

    def test_detect_pii_false_no_issues(self) -> None:
        """AC-09-02: detect_pii=False の場合、PIIを含むデータでも Issue が生成されない。"""
        config = CheckerConfig(detect_pii=False)
        checker = PiiChecker(config)

        texts = ["Email: user@example.com"]
        dataset = self._make_dataset(texts)
        result = checker.check(dataset, text_field="text")

        assert result.issues == [], "detect_pii=False の場合 Issue は発生しないべき"

    def test_detect_pii_false_pii_detected_count_is_zero(self) -> None:
        """AC-09-02: detect_pii=False の場合、pii_detected_count が 0 である。"""
        config = CheckerConfig(detect_pii=False)
        checker = PiiChecker(config)

        texts = ["Email: user@example.com", "SSN: 123-45-6789"]
        dataset = self._make_dataset(texts)
        result = checker.check(dataset, text_field="text")

        assert result.stats.get("pii_detected_count", 0) == 0, (
            "detect_pii=False では pii_detected_count は 0 であるべき"
        )

    def test_detect_pii_false_stats_skipped(self) -> None:
        """AC-09-02: detect_pii=False の場合、stats に skipped フラグが設定される。"""
        config = CheckerConfig(detect_pii=False)
        checker = PiiChecker(config)

        texts = ["Email: user@example.com"]
        dataset = self._make_dataset(texts)
        result = checker.check(dataset, text_field="text")

        assert result.stats.get("skipped") is True, (
            "detect_pii=False では stats['skipped'] が True であるべき"
        )

    # --- AC-09-03: PIIなしデータでの無検出 ---

    def test_no_pii_no_issues(self, checker: PiiChecker) -> None:
        """AC-09-03: PIIパターンを含まないテキストでは issues が空である。"""
        texts = [
            "This is a plain text about machine learning.",
            "Another clean text without any personal information.",
            "Just some regular content here about science.",
        ]
        dataset = self._make_dataset(texts)
        result = checker.check(dataset, text_field="text")

        assert result.issues == [], "PIIパターンなしのテキストで Issue は発生しないべき"

    def test_no_pii_pii_detected_count_is_zero(self, checker: PiiChecker) -> None:
        """AC-09-03: PIIなしデータでは pii_detected_count が 0 である。"""
        texts = ["Clean text", "Another clean text"]
        dataset = self._make_dataset(texts)
        result = checker.check(dataset, text_field="text")

        assert result.stats["pii_detected_count"] == 0, (
            "PIIなしデータでは pii_detected_count が 0 であるべき"
        )

    # --- 電話番号検出 ---

    def test_us_phone_number_detected(self, checker: PiiChecker) -> None:
        """US形式の電話番号を含むテキストで WARNING が発生する。"""
        dataset = self._make_dataset(["Call us at 555-123-4567 for support."])
        result = checker.check(dataset, text_field="text")

        assert result.has_issues, "US電話番号を含む場合 Issue が発生するべき"
        warnings = [i for i in result.issues if i.severity == Severity.WARNING]
        assert len(warnings) >= 1

    def test_us_phone_number_pii_type(self, checker: PiiChecker) -> None:
        """US形式の電話番号検出時、details で 'phone_us' が識別できる。"""
        dataset = self._make_dataset(["Phone: 555-123-4567"])
        result = checker.check(dataset, text_field="text")

        assert result.has_issues
        for issue in result.issues:
            details = issue.details
            found_phone_us = (
                details.get("pii_type") == "phone_us"
                or "phone_us" in details.get("pii_types", {})
                or any(
                    m.get("pii_type") == "phone_us"
                    for m in details.get("pii_matches", [])
                )
            )
            assert found_phone_us, (
                f"details で 'phone_us' PII種別が識別できるべき: {details}"
            )

    def test_jp_phone_number_detected(self, checker: PiiChecker) -> None:
        """JP形式の電話番号を含むテキストで WARNING が発生する。"""
        dataset = self._make_dataset(["お問い合わせは 03-1234-5678 まで。"])
        result = checker.check(dataset, text_field="text")

        assert result.has_issues, "JP電話番号を含む場合 Issue が発生するべき"

    def test_jp_phone_number_pii_type(self, checker: PiiChecker) -> None:
        """JP形式の電話番号検出時、details で 'phone_jp' が識別できる。"""
        dataset = self._make_dataset(["電話: 03-1234-5678"])
        result = checker.check(dataset, text_field="text")

        assert result.has_issues
        for issue in result.issues:
            details = issue.details
            found_phone_jp = (
                details.get("pii_type") == "phone_jp"
                or "phone_jp" in details.get("pii_types", {})
                or any(
                    m.get("pii_type") == "phone_jp"
                    for m in details.get("pii_matches", [])
                )
            )
            assert found_phone_jp, (
                f"details で 'phone_jp' PII種別が識別できるべき: {details}"
            )

    # --- 複数PII種別混在 ---

    def test_multiple_pii_types_in_single_row(self, checker: PiiChecker) -> None:
        """1レコードに複数のPII種別が混在する場合、それぞれ検出される。"""
        # email と ip_address を同一テキストに含む
        texts = ["Contact user@example.com from server 192.168.1.1"]
        dataset = self._make_dataset(texts)
        result = checker.check(dataset, text_field="text")

        assert result.has_issues, "複数PII混在のレコードで Issue が発生するべき"
        assert result.stats["pii_detected_count"] == 1, (
            "PIIを含むレコードが1件なので pii_detected_count は 1 であるべき"
        )

    def test_multiple_rows_with_pii(self, checker: PiiChecker) -> None:
        """複数レコードに PII が含まれる場合、すべての行インデックスが含まれる。"""
        texts = [
            "user1@example.com",
            "Clean text",
            "user2@test.org",
            "Clean again",
            "user3@demo.net",
        ]
        dataset = self._make_dataset(texts)
        result = checker.check(dataset, text_field="text")

        assert result.has_issues, "PII を含むレコードで Issue が発生するべき"
        affected_indices = sorted(
            {idx for issue in result.issues for idx in issue.row_indices}
        )
        assert 0 in affected_indices, "index 0 (user1@example.com) が検出されるべき"
        assert 2 in affected_indices, "index 2 (user2@test.org) が検出されるべき"
        assert 4 in affected_indices, "index 4 (user3@demo.net) が検出されるべき"
        assert 1 not in affected_indices, "index 1 (Clean text) は検出されないべき"
        assert 3 not in affected_indices, "index 3 (Clean again) は検出されないべき"
        assert result.stats["pii_detected_count"] == 3

    def test_pii_detected_count_reflects_affected_records(
        self, checker: PiiChecker
    ) -> None:
        """pii_detected_count が PII を含むレコード数を反映している。"""
        dataset = self._make_dataset([
            "Email: user@example.com",       # index 0: PII あり
            "Clean text about nothing.",     # index 1: PIIなし
            "Call 555-111-2222 for info.",   # index 2: PII あり
        ])
        result = checker.check(dataset, text_field="text")

        assert result.stats["pii_detected_count"] == 2, (
            "PII を含むレコードが2件なので pii_detected_count は 2 であるべき"
        )

    # --- None値スキップ ---

    def test_none_values_are_skipped(self, checker: PiiChecker) -> None:
        """None値のレコードはスキップされ、検出に影響しない。"""
        dataset = Dataset.from_dict({"text": [None, "user@example.com", None]})
        result = checker.check(dataset, text_field="text")

        assert result.has_issues, "index 1 にPIIがあるため Issue が発生するべき"
        affected_indices = [idx for issue in result.issues for idx in issue.row_indices]
        assert 1 in affected_indices, "index 1 が検出されるべき"
        assert 0 not in affected_indices, "None の index 0 は検出されないべき"
        assert 2 not in affected_indices, "None の index 2 は検出されないべき"

    def test_none_only_no_issues(self, checker: PiiChecker) -> None:
        """None値のみのデータセットでは Issue が発生しない。"""
        dataset = Dataset.from_dict({"text": [None, None, None]})
        result = checker.check(dataset, text_field="text")

        assert result.issues == [], "None値のみのデータで Issue は発生しないべき"
        assert result.stats.get("pii_detected_count", 0) == 0

    # --- 空データセット ---

    def test_empty_dataset_no_issues(self, checker: PiiChecker) -> None:
        """空の Dataset では issues が空である。"""
        dataset = self._make_dataset([])
        result = checker.check(dataset, text_field="text")

        assert result.issues == [], "空データセットで Issue は発生しないべき"

    def test_empty_dataset_pii_detected_count_is_zero(
        self, checker: PiiChecker
    ) -> None:
        """空の Dataset では pii_detected_count が 0 である。"""
        dataset = self._make_dataset([])
        result = checker.check(dataset, text_field="text")

        assert result.stats["pii_detected_count"] == 0, (
            "空データセットでは pii_detected_count が 0 であるべき"
        )

    # --- stats["pii_detected_count"] の検証 ---

    def test_pii_detected_count_single_pii_record(
        self, checker: PiiChecker
    ) -> None:
        """PII を含むレコードが1件の場合、pii_detected_count が 1 である。"""
        dataset = self._make_dataset([
            "user@example.com",
            "No PII here at all really.",
        ])
        result = checker.check(dataset, text_field="text")

        assert result.stats["pii_detected_count"] == 1

    def test_pii_detected_count_all_pii_records(self, checker: PiiChecker) -> None:
        """全レコードに PII が含まれる場合、pii_detected_count がレコード数と一致する。"""
        dataset = self._make_dataset([
            "admin@example.com",
            "support@domain.co.jp",
            "info@company.org",
        ])
        result = checker.check(dataset, text_field="text")

        assert result.stats["pii_detected_count"] == 3

    def test_pii_detected_count_no_pii(self, checker: PiiChecker) -> None:
        """PIIなしの場合、pii_detected_count が 0 である。"""
        dataset = self._make_dataset([
            "Clean text one.",
            "Clean text two.",
        ])
        result = checker.check(dataset, text_field="text")

        assert result.stats["pii_detected_count"] == 0

    # --- checker_name の検証 ---

    def test_checker_name_is_pii(self, checker: PiiChecker) -> None:
        """checker_name が 'pii' であること。"""
        dataset = self._make_dataset(["plain text"])
        result = checker.check(dataset, text_field="text")

        assert result.checker_name == "pii", (
            f"checker_name は 'pii' であるべき: {result.checker_name}"
        )

    def test_checker_name_pii_when_detect_off(self) -> None:
        """detect_pii=False の場合も checker_name が 'pii' であること。"""
        config = CheckerConfig(detect_pii=False)
        checker = PiiChecker(config)
        dataset = self._make_dataset(["plain text"])
        result = checker.check(dataset, text_field="text")

        assert result.checker_name == "pii"

    def test_issue_checker_field_matches_name(self, checker: PiiChecker) -> None:
        """Issue.checker フィールドが CheckResult.checker_name と一致すること。"""
        texts = ["user@example.com"]
        dataset = self._make_dataset(texts)
        result = checker.check(dataset, text_field="text")

        for issue in result.issues:
            assert issue.checker == "pii", (
                f"Issue.checker は 'pii' であるべき: {issue.checker}"
            )

    # --- その他のPII種別検出 ---

    def test_ssn_detected(self, checker: PiiChecker) -> None:
        """SSN（社会保障番号）パターンを含むテキストで WARNING が発生する。"""
        dataset = self._make_dataset(["ID number: 123-45-6789"])
        result = checker.check(dataset, text_field="text")

        assert result.has_issues, "SSNを含む場合 Issue が発生するべき"
        warnings = [i for i in result.issues if i.severity == Severity.WARNING]
        assert len(warnings) >= 1

    def test_ip_address_detected(self, checker: PiiChecker) -> None:
        """IPアドレスパターンを含むテキストで WARNING が発生する。"""
        dataset = self._make_dataset(["Server IP: 192.168.1.100"])
        result = checker.check(dataset, text_field="text")

        assert result.has_issues, "IPアドレスを含む場合 Issue が発生するべき"
        warnings = [i for i in result.issues if i.severity == Severity.WARNING]
        assert len(warnings) >= 1

    def test_credit_card_detected(self, checker: PiiChecker) -> None:
        """クレジットカード番号パターンを含むテキストで WARNING が発生する。"""
        dataset = self._make_dataset(["Card number: 1234-5678-9012-3456"])
        result = checker.check(dataset, text_field="text")

        assert result.has_issues, "クレジットカード番号を含む場合 Issue が発生するべき"
        warnings = [i for i in result.issues if i.severity == Severity.WARNING]
        assert len(warnings) >= 1
