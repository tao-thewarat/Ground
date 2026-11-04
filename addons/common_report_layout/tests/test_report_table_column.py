from odoo import Command
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from .common import MODULE, ReportLayoutCommon


@tagged("post_install", "-at_install")
class TestReportTableColumn(ReportLayoutCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.table_document = cls._create_template(
            "test_report_table_document",
            """
            <t t-name="test_report_table_document">
                <span t-out="o.name"/>
                <table class="table o_main_table"><tr><td>CORE TABLE</td></tr></table>
            </t>
            """,
        )
        cls.report_table = cls._create_report(
            "test_report_table",
            f"""
            <t t-name="test_report_table">
                <t t-call="web.html_container">
                    <t t-foreach="docs" t-as="o">
                        <t t-call="{MODULE}.test_report_table_document"/>
                    </t>
                </t>
            </t>
            """,
        )
        cls.th = cls.env.ref("base.th")
        cls.partner.child_ids = [
            Command.create(
                {"name": "Child A", "email": "a@test.com", "country_id": cls.th.id}
            ),
            Command.create({"name": "Child B"}),
        ]
        cls.table_config = cls.Config.create(
            {
                "name": "Table Config",
                "action_report_id": cls.report_table.id,
                "line_field_id": cls._get_field("res.partner", "child_ids").id,
                "table_column_ids": [
                    Command.create(
                        {"name": "Contact", "field_path": "name", "width": 50}
                    ),
                    Command.create(
                        {
                            "name": "Email",
                            "field_path": "email",
                            "width": 30,
                            "header_alignment": "center",
                            "alignment": "right",
                        }
                    ),
                    Command.create(
                        {
                            "name": "Country Code",
                            "field_path": "country_id.code",
                            "width": 20,
                            "is_text_wrap": False,
                        }
                    ),
                    Command.create(
                        {
                            "name": "Hidden",
                            "field_path": "phone",
                            "width": 40,
                            "is_visible": False,
                        }
                    ),
                ],
            }
        )

    def _render_table(self):
        html, _ = (
            self.env["ir.actions.report"]
            .with_context(report_config=self.table_config)
            ._render_qweb_html(self.report_table.report_name, self.partner.ids)
        )
        return html.decode()

    def test_line_model_and_total_width(self):
        self.assertEqual(self.table_config.line_model, "res.partner")
        self.assertEqual(self.table_config.table_total_width, 100)
        self.table_config.line_source = "code"
        self.assertFalse(self.table_config.line_model)
        self.table_config.line_model_id = self.env["ir.model"]._get("res.country")
        self.assertEqual(self.table_config.line_model, "res.country")

    def test_check_total_width(self):
        self.table_config.table_column_ids[0].width = 60
        with self.assertRaises(ValidationError):
            self.table_config.is_table_columns = True

    def test_check_field_path(self):
        with self.assertRaises(ValidationError):
            self.table_config.table_column_ids[0].field_path = "country_id.no_field"
        with self.assertRaises(ValidationError):
            self.table_config.table_column_ids[0].field_path = "name.length"

    def test_find_table_view_follows_calls(self):
        report_view = self.env.ref(self.report_table.report_name)
        self.assertEqual(
            self.table_config._find_table_view(report_view), self.table_document
        )
        no_table = self.env.ref(self.report_lang.report_name)
        self.assertFalse(self.table_config._find_table_view(no_table))

    def test_table_view_follows_toggle(self):
        self.table_config.is_table_columns = True
        view = self.table_config.table_view_id
        self.assertEqual(view.inherit_id, self.table_document)

        self.table_config.is_table_columns = False
        self.assertFalse(self.table_config.table_view_id)
        self.assertFalse(view.exists())

    def test_table_view_requires_items_table(self):
        self.config.write(
            {
                "line_field_id": self._get_field("res.partner", "child_ids").id,
                "table_column_ids": [
                    Command.create({"name": "Name", "field_path": "name", "width": 100})
                ],
            }
        )
        with self.assertRaises(UserError):
            self.config.is_table_columns = True

    def test_render_columns_instead_of_core_table(self):
        self.assertIn("CORE TABLE", self._render_table())

        self.table_config.is_table_columns = True
        html = self._render_table()
        self.assertNotIn("CORE TABLE", html)
        self.assertIn("Contact", html)
        self.assertIn("Country Code", html)
        self.assertNotIn("Hidden", html)
        self.assertIn("Child A", html)
        self.assertIn("a@test.com", html)
        self.assertIn("TH", html)
        self.assertIn("text-end", html)
        self.assertIn("text-nowrap", html)
        self.assertIn("width: 50.0%", html)

        self.assertLess(html.index("Child A"), html.index("Child B"))

        self.table_config.line_domain = "[('email', '!=', False)]"
        html = self._render_table()
        self.assertIn("Child A", html)
        self.assertNotIn("Child B", html)

    def test_get_table_lines_from_code(self):
        self.table_config.write(
            {
                "line_source": "code",
                "line_model_id": self.env["ir.model"]._get("res.partner").id,
                "line_code": "result = doc.child_ids.filtered(lambda c: not c.email)",
            }
        )
        lines = self.table_config._get_table_lines(self.partner)
        self.assertEqual(lines.mapped("name"), ["Child B"])

        self.table_config.line_code = "result = doc.country_id"
        with self.assertRaises(UserError):
            self.table_config._get_table_lines(self.partner)

        self.table_config.line_code = "result = [1, 2]"
        with self.assertRaises(UserError):
            self.table_config._get_table_lines(self.partner)

    def test_line_code_example(self):
        self.table_config.write(
            {
                "line_source": "code",
                "line_model_id": self.env["ir.model"]._get("res.partner").id,
            }
        )
        example = self.table_config._get_line_code_example()
        self.assertIn("result = doc.child_ids\n", example)
        self.assertIn("(res.partner)", example)

        self.table_config.line_code = example
        lines = self.table_config._get_table_lines(self.partner)
        self.assertEqual(lines, self.partner.child_ids)

        self.table_config.line_code = False
        self.table_config._onchange_line_source()
        self.assertEqual(self.table_config.line_code, example)
        self.table_config.line_code = "result = doc.child_ids[:1]"
        self.table_config._onchange_line_source()
        self.assertEqual(self.table_config.line_code, "result = doc.child_ids[:1]")

    def test_display_value(self):
        child_a, child_b = self.partner.child_ids.sorted("name")
        Column = self.env["report.table.column"]

        def value(path, line):
            column = Column.new(
                {"report_config_id": self.table_config.id, "field_path": path}
            )
            return str(column._get_display_value(line))

        self.assertEqual(value("country_id", child_a), self.th.display_name)
        self.assertEqual(value("country_id.code", child_a), "TH")
        self.assertEqual(value("country_id.code", child_b), "")
        self.assertEqual(value("email", child_b), "")
        column = Column.new(
            {
                "report_config_id": self.table_config.id,
                "field_path": "email",
                "default_value": "-",
            }
        )
        self.assertEqual(column._get_display_value(child_b), "-")
        self.assertEqual(str(column._get_display_value(child_a)), "a@test.com")
        self.assertEqual(value("is_company", child_b), "")
        child_b.is_company = True
        self.assertEqual(value("is_company", child_b), "✓")
        self.assertEqual(value("color", child_b), "0")
        self.assertIn("Child A", value("child_ids.name", self.partner))

    def test_css_class_header_and_value(self):
        email = self.table_config.table_column_ids.filtered(
            lambda c: c.field_path == "email"
        )
        self.assertEqual(email._get_css_class(header=True), "text-center")
        self.assertEqual(email._get_css_class(), "text-end")
        code = self.table_config.table_column_ids.filtered(
            lambda c: c.field_path == "country_id.code"
        )
        self.assertEqual(code._get_css_class(header=True), "text-start text-nowrap")

        self.table_config.is_table_columns = True
        html = self._render_table()
        self.assertRegex(html, r'<th class="text-center"[^>]*>\s*<span>Email</span>')

    def test_line_label(self):
        child = self.partner.child_ids[0]
        self.assertEqual(self.table_config._get_table_line_label(child), child.name)
        country = self.th
        self.assertEqual(self.table_config._get_table_line_label(country), "Thailand")

    def test_load_default_columns(self):
        self.table_config.button_load_default_columns()
        columns = self.table_config.table_column_ids
        self.assertEqual(columns.mapped("field_path"), ["name"])
        self.assertEqual(columns.width, 100)

    def test_row_numbers(self):
        class Line:
            _fields = {"display_type": None}

            def __init__(self, display_type=False):
                self.display_type = display_type

        lines = [Line("line_section"), Line(), Line("line_note"), Line(), Line()]
        self.assertEqual(
            self.table_config._get_row_numbers(lines), [None, 1, None, 2, 3]
        )
        self.assertEqual(
            self.table_config._get_row_numbers(self.partner.child_ids), [1, 2]
        )

    def test_render_row_number_column(self):
        self.table_config.is_table_columns = True
        self.assertEqual(self.table_config.row_number_title, "No.")
        self.assertNotIn('name="th_row_number"', self._render_table())

        self.table_config.write({"is_row_number": True, "row_number_title": "ลำดับ"})
        html = self._render_table()
        self.assertIn('name="th_row_number"', html)
        self.assertIn("ลำดับ", html)
        self.assertEqual(html.count('name="td_row_number"'), 2)
        self.assertLess(html.index("ลำดับ"), html.index("Contact"))
        first = html.index('name="td_row_number"')
        self.assertLess(html.index("1", first), html.index("Child A"))
