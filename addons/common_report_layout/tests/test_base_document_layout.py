from odoo.tests import TransactionCase, tagged

from odoo.addons.web.models.base_document_layout import (
    DEFAULT_PRIMARY,
    DEFAULT_SECONDARY,
)


@tagged("post_install", "-at_install")
class TestBaseDocumentLayout(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.ibase_layout = cls.env.ref("common_report_layout.report_layout_ibase")
        cls.wizard = cls.env["base.document.layout"].create(
            {"company_id": cls.company.id}
        )

    def test_onchange_report_layout_id(self):
        self.wizard.report_layout_id = self.ibase_layout
        self.wizard._onchange_report_layout_id()
        self.assertTrue(self.wizard.is_ibase_layout)
        self.assertTrue(self.company.is_ibase_layout)
        self.assertEqual(self.company.report_tables_id, "ibase")
        self.assertEqual(
            self.wizard.external_report_layout_id, self.ibase_layout.view_id
        )

        self.wizard.report_layout_id = self.env["report.layout"].search(
            [("id", "!=", self.ibase_layout.id)], limit=1
        )
        self.wizard._onchange_report_layout_id()
        self.assertFalse(self.company.is_ibase_layout)

    def test_onchange_company_id(self):
        self.company.tertiary_color = False
        self.wizard._onchange_company_id()
        self.assertEqual(self.wizard.tertiary_color, "#000000")

        self.company.tertiary_color = "#123456"
        self.wizard._onchange_company_id()
        self.assertEqual(self.wizard.tertiary_color, "#123456")

    def test_onchange_custom_colors(self):
        self.company.logo = self.company._default_company_stamp()
        self.wizard.write({"custom_colors": False, "tertiary_color": "#123456"})
        self.wizard._onchange_custom_colors()
        self.assertEqual(self.wizard.tertiary_color, "#000000")
        self.assertEqual(
            self.wizard.primary_color, self.wizard.logo_primary_color or DEFAULT_PRIMARY
        )
        self.assertEqual(
            self.wizard.secondary_color,
            self.wizard.logo_secondary_color or DEFAULT_SECONDARY,
        )

    def test_compute_preview(self):
        self.wizard.report_layout_id = self.ibase_layout
        self.wizard._compute_preview()
        self.assertTrue(self.wizard.preview)
