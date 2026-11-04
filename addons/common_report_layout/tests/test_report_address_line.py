from odoo.tests import tagged

from .common import ReportLayoutCommon


@tagged("post_install", "-at_install")
class TestReportAddressLine(ReportLayoutCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.line = cls.env["report.address.line"].create(
            {
                "report_config_id": cls.config.id,
                "name": "Customer",
                "field_id": cls._get_field("res.partner", "commercial_partner_id").id,
                "is_label_bold": True,
                "column_width": "2",
            }
        )

    def test_default_address_format(self):
        self.company.country_id = self.env.ref("base.th")
        line = self.env["report.address.line"].create(
            {"report_config_id": self.config.id, "name": "Default"}
        )
        self.assertEqual(line.address_format, self.company.country_id.address_format)

    def test_clean_report_address_format(self):
        res = self.line._clean_report_address_format(
            "%(street)s\n%(city)s\n%(unknown)s\n100%", {"street": "1", "city": "2"}
        )
        self.assertEqual(res, "%(street)s\n%(city)s\n100")

    def test_clean_report_address_format_custom(self):
        self.line.write({"is_custom_format": True, "address_format": "%(city)s"})
        res = self.line._clean_report_address_format(
            "%(street)s\n%(city)s", {"street": "1", "city": "2"}
        )
        self.assertEqual(res, "%(city)s")

    def test_get_report_address(self):
        res = self.line._get_report_address(self.partner)
        self.assertIn("1 Test Road", res)
        self.assertIn("Bangkok", res)

        self.line.write(
            {"is_custom_format": True, "address_format": "%(street)s\n%(city)s"}
        )
        res = self.line._get_report_address(self.partner)
        self.assertIn("1 Test Road<br", res)
        self.assertTrue(res.endswith("Bangkok"))

    def test_prepare_address_vals(self):
        vals = self.line._prepare_address_vals(self.partner)
        self.assertEqual(vals["key"], "Customer")
        self.assertIn("Bangkok", vals["value"])
        self.assertTrue(vals["label_bold"])
        self.assertFalse(vals["value_bold"])
        self.assertTrue(vals["wrap"])
        self.assertEqual(vals["col_w"], "col-2")
