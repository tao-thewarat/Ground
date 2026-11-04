from unittest.mock import patch

from odoo.tests import tagged

from .common import ReportLayoutCommon


@tagged("post_install", "-at_install")
class TestReportCopyLine(ReportLayoutCommon):
    def test_create_updates_copy_lang(self):
        with patch.object(type(self.Config), "_update_copy_lang") as mock:
            self.env["report.copy.line"].create(
                [
                    {"report_config_id": self.config.id, "copy_type": "main"},
                    {"report_config_id": self.config.id, "copy_type": "copy"},
                ]
            )
        mock.assert_called_once()

    def test_prepare_copy_vals(self):
        line = self.env["report.copy.line"].create(
            {
                "report_config_id": self.config.id,
                "doc_sequence": 2,
                "name": "Copy",
                "title_name": "Invoice",
                "is_bold": True,
                "copy_type": "copy",
            }
        )
        self.assertEqual(
            line._prepare_copy_vals(),
            {"doc_sequence": 2, "name": "Copy", "title_name": "Invoice", "bold": True},
        )
