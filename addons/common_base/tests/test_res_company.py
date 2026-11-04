from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestResCompany(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env["res.company"].create(
            {
                "name": "Test Company",
                "vat": "1234567890123",
                "street": "1 Test Road",
                "city": "Bangkok",
            }
        )

    def test_th_split_tax_number(self):
        self.assertEqual(
            self.company.th_split_tax_number(),
            self.company.partner_id.th_split_tax_number(),
        )
        self.assertEqual(
            self.company.th_split_tax_number("53"),
            ["1", "23", "4", "567", "89012", "3"],
        )

    def test_prepare_display_address(self):
        self.assertEqual(
            self.company._prepare_display_address(),
            self.company.partner_id._prepare_display_address(),
        )
        _, args = self.company._prepare_display_address(without_name=True)
        self.assertEqual(args["parent_name"], "")
        self.assertEqual(args["city"], "Bangkok")
