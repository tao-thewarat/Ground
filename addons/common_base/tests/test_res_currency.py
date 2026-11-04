from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestResCurrency(TransactionCase):
    def test_float_split_amount_str(self):
        Currency = self.env["res.currency"]
        self.env.company.currency_id.decimal_places = 2
        self.assertEqual(Currency.float_split_amount_str(1234.5), ("1234", "50"))
        self.assertEqual(Currency.float_split_amount_str(1234.5, 3), ("1234", "500"))
