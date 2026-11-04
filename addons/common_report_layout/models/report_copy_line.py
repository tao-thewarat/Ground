from odoo import api, fields, models


class ReportCopyLine(models.Model):
    _name = "report.copy.line"
    _description = "Report Copy Line"
    _order = "doc_sequence"

    report_config_id = fields.Many2one(
        comodel_name="report.config",
        ondelete="cascade",
        index=True,
        copy=False,
    )
    doc_sequence = fields.Integer(
        string="Page",
    )
    title_name = fields.Char(
        string="Title",
        translate=True,
    )
    name = fields.Char(
        string="Label",
        translate=True,
    )
    is_bold = fields.Boolean(
        string="Bold",
        help="Enable to display the text in bold on the PDF report. "
        "Disable to use normal (regular) font weight.",
    )
    copy_type = fields.Selection(
        selection=[
            ("main", "Origin Document"),
            ("copy", "Copy Document"),
        ],
        string="Type",
    )

    def _prepare_copy_vals(self):
        return {
            "doc_sequence": self.doc_sequence,
            "name": self.name,
            "title_name": self.title_name,
            "bold": self.is_bold,
        }

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)

        for rec in res.report_config_id:
            rec._update_copy_lang()

        return res
