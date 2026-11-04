from odoo import api, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    def th_split_tax_number(self, option="1") -> list | None:
        self.ensure_one()
        if self.vat and len(self.vat) == 13:
            if option == "1":  # pylint: disable=no-else-return
                card_1 = self.vat[0]
                card_2 = self.vat[1:5]
                card_3 = self.vat[5:10]
                card_4 = self.vat[10:12]
                card_5 = self.vat[12]
                return [card_1, card_2, card_3, card_4, card_5]
            elif option == "2":
                card_1 = self.vat[0]
                card_2 = self.vat[1:5]
                card_3 = self.vat[5:10]
                card_4 = self.vat[10:12]
                card_5 = self.company_id.vat[12]
                return [card_1, card_2, card_3, card_4, card_5]
            elif option == "53":
                card_1 = self.vat[0]
                card_2 = self.vat[1:3]
                card_3 = self.vat[3]
                card_4 = self.vat[4:7]
                card_5 = self.vat[7:12]
                card_6 = self.vat[12]
                return [card_1, card_2, card_3, card_4, card_5, card_6]
        return None

    @api.model
    def _get_address_format(self):
        res = super()._get_address_format()
        if self.env.context.get("custom_format"):
            return self.env.context.get("custom_format")
        return res

    def _get_extra_address_format(self, **kwargs):
        self.ensure_one()
        return {
            "partner_name": self.name,
            "vat": self.vat or "",
            **kwargs,
        }

    def _prepare_display_address(self, without_name: bool = False):
        address_format, args = super()._prepare_display_address(
            without_name=without_name
        )
        args.update(self._get_extra_address_format())
        return address_format, args
