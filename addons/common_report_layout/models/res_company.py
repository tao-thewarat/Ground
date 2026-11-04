from odoo import api, fields, models
from odoo.tools import BinaryBytes, file_open


class ResCompany(models.Model):
    _inherit = "res.company"

    @api.model
    def _default_company_stamp(self):
        with file_open("base/static/img/res_company_logo.png", "rb") as file:
            return BinaryBytes(file.read(), filename="stamp.png")

    font = fields.Selection(
        selection_add=[("Sarabun", "Sarabun")],
        default="Sarabun",
    )
    report_tables_id = fields.Selection(
        selection_add=[("ibase", "IBase")],
        ondelete={"ibase": "set default"},
    )
    tertiary_color = fields.Char(
        copy=False,
    )
    company_stamp = fields.Binary(
        default=lambda self: self._default_company_stamp(),
    )
    shading_option = fields.Selection(
        selection=[
            ("0", "0 %"),
            ("20", "20 %"),
            ("40", "40 %"),
            ("60", "60 %"),
            ("80", "80 %"),
            ("100", "100 %"),
        ],
        default="100",
        string="Shading Line",
    )
    shading_stamp = fields.Selection(
        selection=[
            ("25", "25 %"),
            ("50", "50 %"),
            ("75", "75 %"),
            ("100", "100 %"),
        ],
        default="100",
    )
    is_ibase_layout = fields.Boolean()

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        style_fields = {
            "tertiary_color",
            "company_stamp",
            "shading_option",
            "shading_stamp",
        }
        if any(not style_fields.isdisjoint(values) for values in vals_list):
            self._update_asset_style()
        return res

    def write(self, values):
        res = super().write(values)
        style_fields = {
            "tertiary_color",
            "company_stamp",
            "shading_option",
            "shading_stamp",
        }
        if not style_fields.isdisjoint(values):
            self._update_asset_style()
        return res
