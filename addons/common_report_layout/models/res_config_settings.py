from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    is_ibase_layout = fields.Boolean(
        related="company_id.is_ibase_layout",
    )
