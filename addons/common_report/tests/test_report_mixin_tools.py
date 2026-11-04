from datetime import date

from odoo.tests import TransactionCase, tagged

from odoo.addons.common_readme.tools.date_tools import get_locale_date_format


@tagged("post_install", "-at_install")
class TestReportMixinTools(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Tools = cls.env["report.mixin.tools"]

    def test_get_report_locale_date(self):
        dt = date(2026, 1, 2)
        self.assertEqual(
            self.Tools.get_report_locale_date(dt, "%d/%m/%Y", True), "02/01/2569"
        )
        self.assertEqual(
            self.Tools.get_report_locale_date(dt),
            get_locale_date_format(self.env, dt, "", False, ""),
        )

    def test_get_partner_legend(self):
        partner = self.env["res.partner"].create(
            {"name": "Test Partner", "city": "Bangkok"}
        )
        self.assertEqual(self.Tools._get_partner_legend(partner, "city"), "Bangkok")
        self.assertEqual(self.Tools._get_partner_legend(partner, "unknown"), "")
