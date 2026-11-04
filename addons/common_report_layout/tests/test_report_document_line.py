from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import ReportLayoutCommon


@tagged("post_install", "-at_install")
class TestReportDocumentLine(ReportLayoutCommon):
    def _create_line(self, field_path, **vals):
        return self.env["report.document.line"].create(
            {
                "report_config_id": self.config.id,
                "name": "Label",
                "field_path": field_path,
                **vals,
            }
        )

    def test_check_field_path(self):
        with self.assertRaises(ValidationError):
            self._create_line("no_field")
        with self.assertRaises(ValidationError):
            self._create_line("name.length")

    def test_get_document_data_char(self):
        line = self._create_line("name", column_width="3")
        self.assertEqual(
            line._get_document_data(self.partner),
            {"key": "Label", "value": "Test Partner", "col_w": "col-3"},
        )

    def test_get_document_data_default_value(self):
        line = self._create_line("ref", default_value="-")
        self.assertEqual(line._get_document_data(self.partner)["value"], "-")
        line = self._create_line("country_id.code", default_value="-")
        self.assertEqual(line._get_document_data(self.partner)["value"], "-")

    def test_get_document_data_relational(self):
        line = self._create_line("commercial_partner_id.name")
        self.assertEqual(line._get_document_data(self.partner)["value"], "Test Partner")

    def test_get_document_data_relational_record(self):
        self.partner.country_id = self.env.ref("base.th")
        line = self._create_line("commercial_partner_id.country_id")
        self.assertEqual(line._get_document_data(self.partner)["value"], "Thailand")

    def test_get_document_data_many_values(self):
        self.partner.child_ids = [(0, 0, {"name": "Child A"}), (0, 0, {"name": "B"})]
        line = self._create_line("child_ids.name")
        value = line._get_document_data(self.partner)["value"]
        self.assertIn("Child A", value)
        self.assertIn(", ", value)

    def test_get_document_data_date(self):
        self.config.write(
            {"is_locale_date": True, "format_options": "custom", "date_format": "%Y"}
        )
        line = self._create_line("create_date")
        self.assertEqual(
            line._get_document_data(self.partner)["value"],
            str(self.partner.create_date.year),
        )

    def test_prepare_document_vals(self):
        line = self._create_line("name", is_label_bold=True)
        self.assertEqual(
            line._prepare_document_vals(self.partner),
            {
                "key": "Label",
                "value": "Test Partner",
                "label_bold": True,
                "value_bold": False,
                "col_w": "col-4",
            },
        )
