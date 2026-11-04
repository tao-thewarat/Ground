from unittest.mock import patch

from odoo.tests import tagged

from .common import ReportLayoutCommon


@tagged("post_install", "-at_install")
class TestIrActionsReport(ReportLayoutCommon):
    def _render_and_capture_config(self, report, res_ids):
        captured = {}

        def fake_pre_render(rec, *_args, **_kwargs):
            captured["config"] = rec.env.context.get("report_config")
            return {}, "html"

        Report = self.env["ir.actions.report"]
        with patch.object(type(Report), "_pre_render_qweb_pdf", autospec=True) as mock:
            mock.side_effect = fake_pre_render
            Report._render_qweb_pdf(report.report_name, res_ids)
        return captured["config"]

    def test_render_with_company_document(self):
        self.partner.company_id = self.company
        config = self._render_and_capture_config(self.report_lang, self.partner.ids)
        self.assertEqual(config, self.config)

    def test_render_without_company_field(self):
        report = self._create_report(
            "test_report_country",
            '<t t-name="test_report_country"><span/></t>',
            model="res.country",
        )
        config = self.Config.create({"name": "Country", "action_report_id": report.id})
        country = self.env.ref("base.th")
        self.assertEqual(self._render_and_capture_config(report, country.ids), config)

    def test_render_without_documents(self):
        self.assertEqual(
            self._render_and_capture_config(self.report_lang, None), self.config
        )

    def test_render_not_ibase_layout(self):
        self.company.is_ibase_layout = False
        self.assertIsNone(
            self._render_and_capture_config(self.report_lang, self.partner.ids)
        )

    def test_render_skip_report_config(self):
        Report = self.env["ir.actions.report"].with_context(skip_get_report_config=True)
        with patch.object(
            type(Report), "_pre_render_qweb_pdf", return_value=({}, "html")
        ) as mock:
            Report._render_qweb_pdf(self.report_lang.report_name, self.partner.ids)
        mock.assert_called_once()

    def test_get_paperformat(self):
        report = self.report_lang
        self.assertEqual(report.get_paperformat(), self.company.paperformat_id)
        self.assertEqual(
            report.with_context(report_config=self.config).get_paperformat(),
            self.env.ref("common_report_layout.ibase_custom_paperformat"),
        )

    def test_get_rendering_context(self):
        Report = self.env["ir.actions.report"]
        res = Report._get_rendering_context(self.report_lang, self.partner.ids, {})
        self.assertNotIn("col_address", res)

        self.config.write({"session_width": "4", "is_qr_code": True, "qr_label": "QR"})
        res = Report.with_context(report_config=self.config)._get_rendering_context(
            self.report_lang, self.partner.ids, {}
        )
        self.assertEqual(res["col_address"], "col-4")
        self.assertEqual(res["col_detail"], "col-8")
        self.assertTrue(res["is_qr_code"])
        self.assertEqual(res["qr_label"], "QR")
        self.assertFalse(res["show_copy"])
        self.assertEqual(res["body_style"], "margin-top: 0.0mm; margin-bottom: 0.0mm;")
        self.assertEqual(res["signature_style"], "position: relative; top: 0.0mm;")
