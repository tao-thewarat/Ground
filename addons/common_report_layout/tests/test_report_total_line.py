from datetime import date
from unittest.mock import patch

from odoo import Command
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from .common import MODULE, ReportLayoutCommon

TOTAL_LINE_MODULE = "odoo.addons.common_report_layout.models.report_total_line"


class FakeDoc(dict):
    """Document read like a record (`doc._fields`, `doc[name]`), standing for an
    invoice, which this module's dependencies do not install."""

    @property
    def _fields(self):
        return self

    def sudo(self):
        return self


@tagged("post_install", "-at_install")
class TestReportTotalLine(ReportLayoutCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.totals_document = cls._create_template(
            "test_report_totals_document",
            """
            <t t-name="test_report_totals_document">
                <span t-out="o.name"/>
                <table class="o_total_table table"><tr><td>CORE TOTALS</td></tr></table>
            </t>
            """,
        )
        cls.report_totals = cls._create_report(
            "test_report_totals",
            f"""
            <t t-name="test_report_totals">
                <t t-call="web.html_container">
                    <t t-foreach="docs" t-as="o">
                        <t t-call="{MODULE}.test_report_totals_document"/>
                    </t>
                </t>
            </t>
            """,
        )
        cls.color_field = cls._get_field("res.partner", "color")
        cls.partner.color = 7
        cls.totals_config = cls.Config.create(
            {
                "name": "Totals Config",
                "action_report_id": cls.report_totals.id,
                "total_line_ids": [
                    Command.create(
                        {
                            "name": "Color Index",
                            "field_id": cls.color_field.id,
                            "is_bold": True,
                        }
                    ),
                    Command.create(
                        {"name": "Taxes", "source": "tax", "is_hide_zero": True}
                    ),
                    Command.create(
                        {
                            "name": "Hidden",
                            "field_id": cls.color_field.id,
                            "is_visible": False,
                        }
                    ),
                ],
            }
        )
        cls.currency = cls.env.company.currency_id
        cls.invoice = FakeDoc(
            name="INV/001",
            tax_totals={
                "subtotals": [
                    {
                        "tax_groups": [
                            {"group_name": "VAT 7%", "tax_amount_currency": 420.0},
                            {"group_name": "VAT 0%", "tax_amount_currency": 0.0},
                        ]
                    }
                ]
            },
            invoice_payments_widget={
                "content": [
                    {
                        "amount": 2000.0,
                        "date": date(2026, 10, 19),
                        "is_refund": False,
                        "is_exchange": 0,
                    },
                    {
                        "amount": 100.0,
                        "date": date(2026, 10, 20),
                        "is_refund": True,
                        "is_exchange": 0,
                    },
                    {
                        "amount": 1.0,
                        "date": date(2026, 10, 21),
                        "is_refund": False,
                        "is_exchange": 1,
                    },
                ]
            },
        )

    def _line(self, **vals):
        return self.env["report.total.line"].create(
            {"report_config_id": self.totals_config.id, "name": "Line", **vals}
        )

    def _render_report(self):
        html, _ = (
            self.env["ir.actions.report"]
            .with_context(report_config=self.totals_config)
            ._render_qweb_html(self.report_totals.report_name, self.partner.ids)
        )
        return html.decode()

    def test_check_field_id(self):
        with self.assertRaises(ValidationError):
            self._line(source="field")
        with self.assertRaises(ValidationError):
            self._line(field_id=self._get_field("res.partner", "name").id)
        self.assertTrue(self._line(source="payment"))

    def test_default_vals_list(self):
        Line = self.env["report.total.line"]
        self.assertEqual(Line._get_default_vals_list("res.partner"), [])
        self.assertEqual(Line._get_default_vals_list(False), [])
        defaults = [
            ("Color", "field", "color", True, False),
            ("Location", "tax", "partner_latitude", False, True),
        ]
        with patch(f"{TOTAL_LINE_MODULE}.DEFAULT_TOTAL_LINES", defaults):
            vals_list = Line._get_default_vals_list("res.partner")
            self.assertEqual(
                vals_list,
                [
                    {
                        "sequence": 0,
                        "name": "Color",
                        "source": "field",
                        "field_id": self.color_field.id,
                        "is_bold": True,
                        "is_hide_zero": False,
                    },
                    {
                        "sequence": 1,
                        "name": "Location",
                        "source": "tax",
                        "field_id": False,
                        "is_bold": False,
                        "is_hide_zero": True,
                    },
                ],
            )
            self.totals_config.button_load_default_totals()
        self.assertEqual(
            self.totals_config.total_line_ids.mapped("name"), ["Color", "Location"]
        )

    def test_field_rows(self):
        line = self.totals_config.total_line_ids[0]
        self.assertEqual(
            line._get_rows(self.partner, self.currency),
            [{"label": "Color Index", "amount": 7, "type": "field", "bold": True}],
        )
        other_model = self._line(
            field_id=self._get_field("res.country", "phone_code").id
        )
        self.assertEqual(
            other_model._get_rows(self.partner, self.currency)[0]["amount"], 0.0
        )
        line.is_hide_zero = True
        self.partner.color = 0
        self.assertEqual(line._get_rows(self.partner, self.currency), [])

    def test_tax_rows(self):
        line = self.totals_config.total_line_ids[1]
        self.assertEqual(
            line._get_rows(self.invoice, self.currency),
            [{"label": "VAT 7%", "amount": 420.0, "type": "tax", "bold": False}],
        )
        line.is_hide_zero = False
        self.assertEqual(len(line._get_rows(self.invoice, self.currency)), 2)
        self.assertEqual(line._get_rows(self.partner, self.currency), [])

    def test_payment_rows(self):
        line = self._line(source="payment")
        rows = line._get_rows(self.invoice, self.currency)
        self.assertEqual([row["amount"] for row in rows], [2000.0, 100.0])
        self.assertEqual([row["is_refund"] for row in rows], [False, True])
        self.assertEqual(rows[0]["date"], date(2026, 10, 19))
        self.assertEqual(line._get_rows(self.partner, self.currency), [])

    def test_totals_currency(self):
        eur = self.env.ref("base.EUR")
        config = self.totals_config
        self.assertEqual(config._get_totals_currency(FakeDoc(currency_id=eur)), eur)
        self.assertEqual(config._get_totals_currency(FakeDoc()), self.currency)
        config.company_id = False
        self.assertEqual(config._get_totals_currency(FakeDoc()), self.currency)

    def test_total_rows_skip_hidden(self):
        rows = self.totals_config._get_total_rows(self.partner)
        self.assertEqual([row["label"] for row in rows], ["Color Index"])

    def test_totals_view_follows_toggle(self):
        self.totals_config.is_totals = True
        view = self.totals_config.totals_view_id
        self.assertEqual(view.inherit_id, self.totals_document)
        self.assertIn("_totals_", view.key)

        self.totals_config.is_totals = False
        self.assertFalse(self.totals_config.totals_view_id)
        self.assertFalse(view.exists())

    def test_totals_view_requires_totals_table(self):
        with self.assertRaises(UserError):
            self.config.is_totals = True

    def test_create_with_totals(self):
        self.totals_config.unlink()
        config = self.Config.create(
            {
                "name": "Created",
                "action_report_id": self.report_totals.id,
                "is_totals": True,
            }
        )
        self.assertEqual(config.totals_view_id.inherit_id, self.totals_document)

    def test_render_totals_instead_of_core(self):
        self.assertIn("CORE TOTALS", self._render_report())

        self.totals_config.is_totals = True
        html = self._render_report()
        self.assertNotIn("CORE TOTALS", html)
        self.assertIn("o_ibase_totals", html)
        self.assertIn("Color Index", html)
        self.assertIn("fw-bold", html)
        self.assertNotIn("Hidden", html)

    def test_render_payments_template(self):
        self._line(source="payment")
        html = str(
            self.env["ir.qweb"]._render(
                f"{MODULE}.ibase_totals",
                {"ibase_totals_config": self.totals_config, "totals_doc": self.invoice},
            )
        )
        self.assertIn("VAT 7%", html)
        self.assertIn("Paid on", html)
        self.assertIn("Reversed on", html)
        self.assertIn("2,000.00", html)
        self.assertNotIn("VAT 0%", html)

    def test_totals_view_updated_in_place(self):
        self.totals_config.is_totals = True
        view = self.totals_config.totals_view_id
        self.totals_config._update_totals_view()
        self.assertEqual(self.totals_config.totals_view_id, view)

    def test_find_totals_view_depth_limit(self):
        calls = ""
        for level in range(5, 0, -1):
            body = calls or '<table class="o_total_table"/>'
            self._create_template(f"test_deep_{level}", f'<t t-name="x">{body}</t>')
            calls = f'<t t-call="{MODULE}.test_deep_{level}"/>'
        top = self.env.ref(f"{MODULE}.test_deep_1")
        self.assertFalse(self.totals_config._find_table_view(top, "o_total_table"))
        second = self.env.ref(f"{MODULE}.test_deep_2")
        self.assertEqual(
            self.totals_config._find_table_view(second, "o_total_table"),
            self.env.ref(f"{MODULE}.test_deep_5"),
        )
