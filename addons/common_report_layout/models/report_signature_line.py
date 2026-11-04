from odoo import fields, models
from odoo.tools import format_date


class ReportSignatureLine(models.Model):
    _name = "report.signature.line"
    _description = "Report Signature Line"
    _order = "sequence"

    sequence = fields.Integer(
        default=10,
    )
    report_config_id = fields.Many2one(
        comodel_name="report.config",
        ondelete="cascade",
        index=True,
        copy=False,
    )
    model_id = fields.Many2one(
        related="report_config_id.model_id",
    )
    name = fields.Char(
        string="Label",
        translate=True,
    )
    label_position = fields.Selection(
        selection=[("top", "Top"), ("bottom", "Bottom")],
        default="top",
        required=True,
        help="Print the label above or below the signature.",
    )
    bottom_label = fields.Char(
        translate=True,
        help="Text printed under the signature before the Sign Date, e.g. 'Date'. "
        "Hidden when empty.",
    )
    field_sign_id = fields.Many2one(
        comodel_name="ir.model.fields",
        string="Sign User",
        ondelete="set null",
    )
    field_date_id = fields.Many2one(
        comodel_name="ir.model.fields",
        string="Sign Date",
        ondelete="set null",
    )
    is_company_stamp = fields.Boolean(
        string="Company Stamp",
        default=False,
    )

    def _get_signature_data(self, res_obj):
        self.ensure_one()
        report_config = self.report_config_id

        def _get_sign_date(res_obj, report_config):
            sign_date = report_config._get_field_attr(res_obj, self.field_date_id.name)

            if not report_config.is_locale_date or not sign_date:
                return format_date(self.env, sign_date)

            return report_config._get_report_date(res_obj, sign_date, strict=False)

        def _get_sign_name(res_obj, report_config):
            field_sign = report_config._get_field_attr(res_obj, self.field_sign_id.name)

            if not field_sign:
                return None

            if field_sign._name == "res.users":
                field_sign = field_sign.partner_id

            return report_config._get_partner_legend(field_sign, "partner_title")

        return {
            "sign_date": _get_sign_date(res_obj, report_config),
            "sign_name": _get_sign_name(res_obj, report_config),
        }

    def _prepare_signature_vals(self, res_obj):
        self.ensure_one()
        res_obj.ensure_one()
        sign_data = self._get_signature_data(res_obj)

        return {
            "label": self.name,
            "label_position": self.label_position,
            "bottom_label": self.bottom_label,
            "sign_name": sign_data.get("sign_name"),
            "sign_date": sign_data.get("sign_date"),
            "company_stamp": self.is_company_stamp,
        }
