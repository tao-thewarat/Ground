from odoo import models


class ResCompany(models.Model):
    _inherit = "res.company"

    def th_split_tax_number(self, option="1"):
        return self.partner_id.th_split_tax_number(option)

    def _prepare_display_address(self, without_name=False):
        self.ensure_one()
        return self.partner_id._prepare_display_address(without_name=without_name)
