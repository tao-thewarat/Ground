from odoo import api, fields, models

from odoo.addons.web.models.base_document_layout import (
    DEFAULT_PRIMARY,
    DEFAULT_SECONDARY,
)


class BaseDocumentLayout(models.TransientModel):
    _inherit = "base.document.layout"

    is_ibase_layout = fields.Boolean()
    tertiary_color = fields.Char(
        related="company_id.tertiary_color",
        readonly=False,
    )
    shading_option = fields.Selection(
        related="company_id.shading_option",
        readonly=False,
    )
    company_stamp = fields.Binary(
        related="company_id.company_stamp",
        readonly=False,
    )
    shading_stamp = fields.Selection(
        related="company_id.shading_stamp",
        readonly=False,
    )

    @api.onchange("report_layout_id")
    def _onchange_report_layout_id(self):
        res = super()._onchange_report_layout_id()
        ibase_layout = self.env.ref("common_report_layout.report_layout_ibase")
        for rec in self:
            is_ibase_layout = rec.report_layout_id == ibase_layout
            rec.is_ibase_layout = is_ibase_layout
            rec.company_id.is_ibase_layout = is_ibase_layout
            if is_ibase_layout:
                rec.report_tables_id = "ibase"
        return res

    @api.onchange("company_id")
    def _onchange_company_id(self):
        res = super()._onchange_company_id()
        for rec in self:
            rec.company_stamp = rec.company_id.company_stamp
            rec.tertiary_color = rec.company_id.tertiary_color

            if not rec.tertiary_color:
                rec.tertiary_color = "#000000"
        return res

    @api.depends(
        "report_layout_id",
        "logo",
        "font",
        "primary_color",
        "secondary_color",
        "report_header",
        "report_footer",
        "company_details",
        "report_tables_id",
        "tertiary_color",
        "shading_option",
        "shading_stamp",
    )
    def _compute_preview(self):
        return super()._compute_preview()

    @api.onchange("custom_colors")
    def _onchange_custom_colors(self):
        for rec in self:
            if rec.logo and not rec.custom_colors:
                rec.primary_color = rec.logo_primary_color or DEFAULT_PRIMARY
                rec.secondary_color = rec.logo_secondary_color or DEFAULT_SECONDARY
                rec.tertiary_color = "#000000"
