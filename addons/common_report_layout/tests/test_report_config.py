import base64
from datetime import date
from unittest.mock import MagicMock, patch

from odoo import Command, fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tools import get_lang

from odoo.addons.common_readme.tools.date_tools import get_locale_date_format

from .common import ReportLayoutCommon

CONFIG_MODULE = "odoo.addons.common_report_layout.models.report_config"


class ExtraFooterRecord:
    def _get_extra_footer_template(self, report_config):
        return f"extra_footer_{report_config._name}"


@tagged("post_install", "-at_install")
class TestReportConfig(ReportLayoutCommon):
    def test_default_date_time_format(self):
        lang = get_lang(self.env)
        self.assertEqual(self.config.date_format, lang.date_format)
        self.assertEqual(self.config.time_format, lang.time_format)

    def test_check_unique_report_per_company(self):
        self.Config.create({"name": "No Report"})
        with self.assertRaises(ValidationError):
            self.Config.create(
                {"name": "Duplicate", "action_report_id": self.report_lang.id}
            )

    def test_check_date_format(self):
        self.config.date_format = "%d/%m/%Y"
        with self.assertRaises(ValidationError):
            self.config.date_format = "%d/%m/%Y %H"
        with self.assertRaises(ValidationError):
            self.config.date_format = "%d x %m"

    def test_onchange_action_report_id(self):
        config = self.Config.new({"action_report_id": self.report_t_lang.id})
        config._onchange_action_report_id()
        self.assertEqual(config.name, self.report_t_lang.name)

    def test_onchange_number_of_copies(self):
        config = self.Config.new(
            {
                "number_of_copies": 1,
                "origin_label": "Original",
                "copy_label": "Copy",
                "layout_document_title": "Invoice",
            }
        )
        config._onchange_number_of_copies()
        self.assertEqual(config.copy_line_ids.mapped("name"), ["Original", "Copy"])
        self.assertEqual(config.copy_line_ids.mapped("copy_type"), ["main", "copy"])
        self.assertEqual(config.copy_line_ids.mapped("title_name"), ["Invoice"] * 2)

    def test_update_copy_lang(self):
        self.env["res.lang"]._activate_lang("th_TH")
        self.config.write(
            {
                "copy_line_ids": [
                    Command.create({"name": "Original", "copy_type": "main"}),
                    Command.create({"name": "Copy", "copy_type": "copy"}),
                ],
            }
        )
        self.config.update_field_translations("origin_label", {"th_TH": "ต้นฉบับ"})
        self.config.update_field_translations("copy_label", {"th_TH": "สำเนา"})
        self.config.write({"origin_label": "Original"})

        main, copy = self.config.copy_line_ids.with_context(lang="th_TH")
        self.assertEqual(main.name, "ต้นฉบับ")
        self.assertEqual(copy.name, "สำเนา")
        self.assertFalse(main.title_name)

    def test_get_extra_footer_template(self):
        self.assertFalse(self.config._get_extra_footer_template(self.partner))
        self.assertEqual(
            self.config._get_extra_footer_template(ExtraFooterRecord()),
            "extra_footer_report.config",
        )

    def test_get_paperformat_by_config(self):
        basic = self.env.ref("common_report_layout.ibase_basic_paperformat")
        self.report_lang.extra_footer_spacing = 2

        paperformat = self.config._get_paperformat_by_config()
        self.assertEqual(paperformat.margin_top, basic.margin_top)
        self.assertEqual(paperformat.margin_bottom, basic.margin_bottom + 2)

        self.config.is_qr_code = True
        paperformat = self.config._get_paperformat_by_config()
        self.assertEqual(paperformat.margin_bottom, basic.margin_bottom + 17.5 + 2)

        self.config.write(
            {
                "address_line_ids": [
                    Command.create({"name": "Address", "address_format": "a\nb\nc"})
                ],
                "document_line_ids": [Command.create({"name": "Doc"})],
                "signature_line_ids": [Command.create({"name": "Sign"})],
            }
        )
        paperformat = self.config._get_paperformat_by_config()
        self.assertEqual(paperformat.margin_top, basic.margin_top + 15)
        self.assertEqual(paperformat.header_spacing, basic.header_spacing + 15)
        self.assertEqual(paperformat.margin_bottom, basic.margin_bottom + 22.5 + 2)

    def test_body_position(self):
        basic = self.env.ref("common_report_layout.ibase_basic_paperformat")
        with self.assertRaises(ValidationError):
            self.config.body_gap = -1

        self.config.button_body_offset_up()
        self.config.button_body_offset_up()
        self.config.button_body_gap_increase()
        self.config.button_body_gap_increase()
        self.config.button_body_gap_increase()
        self.config.button_body_gap_decrease()
        self.assertEqual(self.config.body_offset, -2)
        self.assertEqual(self.config.body_gap, 2)
        self.assertEqual(
            self.config._get_body_style(), "margin-top: -2.0mm; margin-bottom: 2.0mm;"
        )

        self.config.write({"body_offset": 5.5, "body_gap": 3})
        paperformat = self.config._get_paperformat_by_config()
        self.assertEqual(paperformat.margin_top, basic.margin_top + 8.5)
        self.assertEqual(paperformat.header_spacing, round(basic.header_spacing + 8.5))

        self.config.body_gap = 0
        self.config.button_body_gap_decrease()
        self.assertEqual(self.config.body_gap, 0)

        self.config.write({"body_offset": 4, "body_gap": 6})
        self.config.button_body_offset_reset()
        self.assertEqual((self.config.body_offset, self.config.body_gap), (0, 6))
        self.config.button_body_gap_reset()
        self.assertEqual(self.config.body_gap, 0)

    def test_signature_offset(self):
        self.config.button_signature_offset_up()
        self.config.button_signature_offset_up()
        self.config.button_signature_offset_down()
        self.assertEqual(self.config.signature_offset, -1)
        self.assertEqual(
            self.config._get_signature_style(), "position: relative; top: -1.0mm;"
        )
        self.config.button_signature_offset_reset()
        self.assertEqual(self.config.signature_offset, 0)

    def test_get_field_attr(self):
        partner2 = self.partner.copy({"name": "Second"})
        self.assertIsNone(self.config._get_field_attr(self.partner, ""))
        self.assertIsNone(self.config._get_field_attr(self.partner.browse(), "name"))
        self.assertEqual(
            self.config._get_field_attr(self.partner, "name"), "Test Partner"
        )
        self.assertEqual(
            self.config._get_field_attr(self.partner | partner2, "name"),
            "Test Partner, Second",
        )

    def test_get_report_date(self):
        dt = date(2026, 1, 2)
        config = self.config
        self.assertEqual(
            config._get_report_date(self.partner, dt),
            get_locale_date_format(self.env, dt),
        )

        config.write(
            {
                "is_locale_date": True,
                "is_be_era": True,
                "format_options": "custom",
                "date_format": "%d/%m/%Y",
                "is_time_format": True,
                "time_format": "%H:%M",
            }
        )
        self.assertEqual(config._get_report_date(self.partner, dt), "02/01/2569")
        self.assertEqual(
            config._get_report_date(
                self.partner, fields.Datetime.to_datetime("2026-01-02 10:30:00")
            ),
            "02/01/2569 10:30",
        )

        config.is_time_format = False
        config.format_options = "by_user"
        user_lang = get_lang(self.env, self.env.user.lang)
        self.assertEqual(
            config._get_report_date(self.partner, dt),
            get_locale_date_format(
                self.env, dt, user_lang.date_format, True, user_lang.iso_code
            ),
        )

        config.write(
            {
                "format_options": "by_partner",
                "field_partner_format_id": self._get_field(
                    "res.partner", "commercial_partner_id"
                ).id,
            }
        )
        partner_lang = self.env["res.lang"]._lang_get("en_US")
        self.assertEqual(
            config._get_report_date(self.partner, dt),
            get_locale_date_format(
                self.env, dt, partner_lang.date_format, True, partner_lang.iso_code
            ),
        )
        self.partner.lang = False
        self.assertEqual(
            config._get_report_date(self.partner, dt),
            get_locale_date_format(self.env, dt, None, True, None),
        )

    def test_get_record_url(self):
        base_url = self.partner.get_base_url()
        self.assertIsNone(self.config._get_record_url(self.partner.browse()))
        self.assertEqual(
            self.config._get_record_url(self.partner),
            f"{base_url}/odoo/res.partner/{self.partner.id}",
        )
        with patch.object(
            type(self.partner), "get_portal_url", create=True, return_value="/my/doc"
        ):
            self.assertEqual(
                self.config._get_record_url(self.partner), f"{base_url}/my/doc"
            )

    def test_get_backend_url(self):
        base_url = self.partner.get_base_url()
        self.assertIsNone(self.config._get_backend_url(self.partner.browse()))
        with patch.object(
            type(self.partner),
            "_get_portal_return_action",
            create=True,
            return_value=MagicMock(path="contacts"),
        ):
            self.assertEqual(
                self.config._get_backend_url(self.partner),
                f"{base_url}/odoo/contacts/{self.partner.id}",
            )

    def test_get_date_qr_code(self):
        config = self.config
        self.assertEqual(config._get_date_qr_code(self.partner), "")
        config.qr_type = "doc_no"
        self.assertEqual(config._get_date_qr_code(self.partner), "Test Partner")
        config.qr_type = "portal"
        self.assertEqual(
            config._get_date_qr_code(self.partner),
            config._get_record_url(self.partner),
        )
        config.qr_type = "doc_link"
        self.assertEqual(
            config._get_date_qr_code(self.partner),
            config._get_backend_url(self.partner),
        )

    def test_generate_qr_config(self):
        self.config.qr_type = "doc_no"
        qr_image = self.config.generate_qr_config(self.partner)
        self.assertTrue(base64.b64decode(qr_image).startswith(b"\x89PNG"))
        with patch(f"{CONFIG_MODULE}.qrcode", None), self.assertRaises(UserError):
            self.config.generate_qr_config(self.partner)

    def test_get_vals_lists(self):
        self.config.write(
            {
                "copy_line_ids": [
                    Command.create({"name": "Original", "doc_sequence": 1})
                ],
                "address_line_ids": [
                    Command.create(
                        {
                            "name": "Customer",
                            "field_id": self._get_field(
                                "res.partner", "commercial_partner_id"
                            ).id,
                        }
                    )
                ],
                "document_line_ids": [
                    Command.create(
                        {
                            "name": "Name",
                            "field_path": "name",
                        }
                    )
                ],
                "signature_line_ids": [Command.create({"name": "Sign"})],
            }
        )
        self.assertEqual(self.config._get_copy_label_list()[0]["name"], "Original")
        self.assertEqual(
            self.config.get_report_address_vals_list(self.partner)[0]["key"],
            "Customer",
        )
        self.assertEqual(
            self.config.get_report_document_vals_list(self.partner)[0]["value"],
            "Test Partner",
        )
        self.assertEqual(
            self.config.get_report_signature_vals_list(self.partner)[0]["label"],
            "Sign",
        )

    def test_get_lang_value(self):
        config = self.config
        self.assertEqual(config._get_lang_value("o.lang"), "o.lang")
        config.report_lang_options = "by_user"
        self.assertEqual(config._get_lang_value("o.lang"), "user.lang or (o.lang)")
        config.write({"report_lang_options": "fixed", "lang_code": "th_TH"})
        self.assertEqual(config._get_lang_value("o.lang"), "'th_TH' or (o.lang)")

    def test_lang_view_t_set(self):
        self.config.write({"report_lang_options": "fixed", "lang_code": "th_TH"})
        view = self.config.lang_view_id
        self.assertIn("'th_TH' or (lang)", view.arch_db)

        self.config.write({"report_lang_options": "by_user"})
        self.assertEqual(self.config.lang_view_id, view)
        self.assertIn("user.lang or (lang)", view.arch_db)
        self.assertIn("Test Partner", self._render_html(self.report_lang))

    def test_lang_view_t_lang(self):
        config = self.Config.create(
            {"name": "T Lang", "action_report_id": self.report_t_lang.id}
        )
        config.write({"report_lang_options": "by_user"})
        self.assertIn("user.lang or (o.lang)", config.lang_view_id.arch_db)
        self.assertIn("Test Partner", self._render_html(self.report_t_lang))

    def test_lang_view_wrapper(self):
        self.config.write({"report_lang_options": "by_user"})
        view = self.config.lang_view_id
        self.assertTrue(view)
        self.assertIsNone(
            self.config._get_lang_arch_db(
                self.env.ref(self.report_wrapper.report_name),
                self.report_wrapper.report_name,
            )
        )
        self.config.write({"action_report_id": self.report_wrapper.id})
        self.assertFalse(view.exists())
        self.config.write({"report_lang_options": "by_report"})
        self.assertFalse(self.config.lang_view_id)

    def test_copy_view(self):
        self.config.write({"is_copy": True, "number_of_copies": 1})
        view = self.config.copy_view_id
        self.assertIn("range(1, 3)", view.arch_db)
        self.assertIn("web.html_container", view.arch_db)
        self.assertEqual(self._render_html(self.report_lang).count("Test Partner"), 2)

        self.config.write({"number_of_copies": 2})
        self.assertEqual(self.config.copy_view_id, view)
        self.assertIn("range(1, 4)", view.arch_db)

        self.config.write({"is_copy": False})
        self.assertFalse(view.exists())

    def test_copy_view_wrapper(self):
        config = self.Config.create(
            {"name": "Wrapper", "action_report_id": self.report_wrapper.id}
        )
        config.write({"is_copy": True, "number_of_copies": 1})
        self.assertIn("/t/t[@t-call]", config.copy_view_id.arch_db)
        self.assertEqual(
            self._render_html(self.report_wrapper).count("Test Partner"), 2
        )

    def test_write_view_errors(self):
        Config = type(self.Config)
        with (
            patch.object(Config, "_update_lang_view", side_effect=ValidationError("")),
            self.assertLogs(CONFIG_MODULE, "ERROR"),
        ):
            self.config.write({"report_lang_options": "by_user"})
        with (
            patch.object(Config, "_update_copy_view", side_effect=UserError("")),
            self.assertLogs(CONFIG_MODULE, "ERROR"),
        ):
            self.config.write({"is_copy": True})

    def test_write_empty(self):
        self.assertTrue(self.Config.browse().write({"name": "Nothing"}))

    def test_layout_hides_standard_informations(self):
        report = self._create_report(
            "test_report_informations",
            """
            <t t-name="test_report_informations">
                <t t-call="web.html_container">
                    <t t-foreach="docs" t-as="o">
                        <t t-call="web.external_layout">
                            <div id="informations">Invoice Date</div>
                        </t>
                    </t>
                </t>
            </t>
            """,
        )
        self.company.external_report_layout_id = self.env.ref(
            "common_report_layout.external_layout_ibase"
        )
        Report = self.env["ir.actions.report"]

        html = Report._render_qweb_html(report.report_name, self.partner.ids)[0]
        self.assertNotIn(b"o_common_report_config", html)

        config = self.Config.create({"name": "Info", "action_report_id": report.id})
        html = Report.with_context(report_config=config)._render_qweb_html(
            report.report_name, self.partner.ids
        )[0]
        self.assertIn(b"o_common_report_config", html)
        self.assertIn(b'id="informations"', html)
