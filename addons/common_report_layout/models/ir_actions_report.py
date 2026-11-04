from odoo import fields, models


class IrActionsReport(models.Model):
    _inherit = "ir.actions.report"

    extra_footer_spacing = fields.Float()

    def _with_report_config(self, report_ref, res_ids):
        """Self with the report configuration of the printed report in the context,
        unless skip_get_report_config is set or it is already there."""
        if self.env.context.get("skip_get_report_config") or self.env.context.get(
            "report_config"
        ):
            return self
        ReportSudo = self.env["ir.actions.report"].sudo()
        ReportConfigSudo = self.env["report.config"].sudo()
        print_report = self._get_report(report_ref)
        report = ReportSudo.search([("id", "=", print_report.id)], limit=1)
        if not report:
            return self

        domain = [("action_report_id", "=", report.id)]
        ref_doc = self.env[report.model].sudo().browse(res_ids)
        if ref_doc and "company_id" in ref_doc._fields:
            domain.append(("company_id", "=", ref_doc[:1].company_id.id))
        elif ref_doc:
            domain.append(("company_id", "=", self.env.company.id))

        report_config = ReportConfigSudo.search(domain, limit=1)
        if report_config.company_id.is_ibase_layout:
            return self.with_context(report_config=report_config)
        return self

    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        """Pass the related report configuration into the context."""
        self = self._with_report_config(report_ref, res_ids)
        return super()._render_qweb_pdf(report_ref, res_ids=res_ids, data=data)

    def _render_qweb_html(self, report_ref, docids, data=None):
        """Same as the PDF, so the HTML preview shows the configured layout."""
        self = self._with_report_config(report_ref, docids)
        return super()._render_qweb_html(report_ref, docids, data=data)

    def get_paperformat(self):
        res = super().get_paperformat()
        if report_config := self.env.context.get("report_config"):
            res = report_config._get_paperformat_by_config()
        return res

    def _get_rendering_context(self, report, docids, data):
        """
        Optimizes report rendering performance by injecting configuration values
        into the rendering context before the report is generated.

        Although these values could be fetched dynamically in the XML templates,
        that approach would trigger repeated database queries — especially when
        generating multiple copies of a report.

        By retrieving the configuration once and injecting it into the context here,
        we avoid redundant queries and ensure consistent values throughout the report.
        """
        res = super()._get_rendering_context(report, docids, data)
        if report_config := self.env.context.get("report_config"):
            res.update(
                {
                    "is_qr_code": report_config.is_qr_code,
                    "qr_label": report_config.qr_label,
                    "is_specific_title": report_config.is_specific_title,
                    "is_locale_date": report_config.is_locale_date,
                    "is_be_era": report_config.is_be_era,
                    "show_copy": report_config.number_of_copies != 0,
                    "col_address": f"col-{int(report_config.session_width)}",
                    "col_detail": f"col-{12 - int(report_config.session_width)}",
                    "body_style": report_config._get_body_style(),
                    "signature_style": report_config._get_signature_style(),
                }
            )
        return res
