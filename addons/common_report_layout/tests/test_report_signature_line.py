from odoo.tests import tagged
from odoo.tools import format_date

from .common import ReportLayoutCommon


@tagged("post_install", "-at_install")
class TestReportSignatureLine(ReportLayoutCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = cls.env["res.users"].create(
            {"name": "Signer", "login": "test_signer"}
        )
        cls.partner.user_id = cls.user

    def _create_line(self, sign_field=None, date_field=None):
        return self.env["report.signature.line"].create(
            {
                "report_config_id": self.config.id,
                "name": "Approved By",
                "field_sign_id": sign_field
                and self._get_field("res.partner", sign_field).id,
                "field_date_id": date_field
                and self._get_field("res.partner", date_field).id,
                "is_company_stamp": True,
            }
        )

    def test_signature_user(self):
        data = self._create_line("user_id", "create_date")._get_signature_data(
            self.partner
        )
        self.assertEqual(data["sign_name"], "")
        self.assertEqual(
            data["sign_date"], format_date(self.env, self.partner.create_date)
        )

    def test_signature_empty(self):
        data = self._create_line()._get_signature_data(self.partner)
        self.assertIsNone(data["sign_name"])
        self.assertEqual(data["sign_date"], "")

    def test_signature_locale_date(self):
        self.config.write(
            {"is_locale_date": True, "format_options": "custom", "date_format": "%Y"}
        )
        data = self._create_line(date_field="create_date")._get_signature_data(
            self.partner
        )
        self.assertEqual(data["sign_date"], str(self.partner.create_date.year))

    def test_prepare_signature_vals(self):
        vals = self._create_line("user_id")._prepare_signature_vals(self.partner)
        self.assertEqual(vals["label"], "Approved By")
        self.assertTrue(vals["company_stamp"])
        self.assertEqual(vals["label_position"], "top")
        self.assertFalse(vals["bottom_label"])

    def test_footer_label_position_and_bottom_label(self):
        def render(**sign):
            return str(
                self.env["ir.qweb"]._render(
                    "common_report_layout.ibase_footer_with_signature",
                    {
                        "company": self.env.company,
                        "signature_style": "position: relative; top: -2.0mm;",
                        "signature_vals_list": [{"label": "Approved", **sign}],
                    },
                )
            )

        html = render(label_position="top", sign_date="01/01/2026")
        self.assertIn('name="signature_label"', html)
        self.assertNotIn('name="signature_label_bottom"', html)
        self.assertIn("top: -2.0mm", html)

        html = render(label_position="bottom", bottom_label="Date", sign_date=False)
        self.assertNotIn('name="signature_label"', html)
        self.assertIn('name="signature_label_bottom"', html)
        self.assertIn("Date", html)
        self.assertIn("....................", html)
