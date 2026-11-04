from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestResPartner(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env["res.company"].create(
            {"name": "Test Company", "vat": "9876543210123"}
        )
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Test Partner",
                "vat": "1234567890123",
                "street": "1 Test Road",
                "city": "Bangkok",
                "company_id": cls.company.id,
            }
        )

    def test_th_split_tax_number(self):
        partner = self.partner
        self.assertEqual(
            partner.th_split_tax_number(), ["1", "2345", "67890", "12", "3"]
        )
        self.assertEqual(
            partner.th_split_tax_number("2"), ["1", "2345", "67890", "12", "3"]
        )
        self.assertEqual(
            partner.th_split_tax_number("53"), ["1", "23", "4", "567", "89012", "3"]
        )
        self.assertIsNone(partner.th_split_tax_number("99"))

    def test_th_split_tax_number_option_2_company_vat(self):
        self.partner.vat = "1234567890120"
        self.assertEqual(self.partner.th_split_tax_number("2")[-1], "3")

    def test_th_split_tax_number_invalid_vat(self):
        self.partner.vat = "123"
        self.assertIsNone(self.partner.th_split_tax_number())
        self.partner.vat = False
        self.assertIsNone(self.partner.th_split_tax_number())

    def test_get_address_format(self):
        Partner = self.env["res.partner"]
        self.assertEqual(
            self.partner._get_address_format(),
            Partner._get_default_address_format(),
        )
        self.assertEqual(
            self.partner.with_context(custom_format="%(city)s")._get_address_format(),
            "%(city)s",
        )
        address_format, _ = self.partner.with_context(
            custom_format="%(street)s"
        )._prepare_display_address()
        self.assertEqual(address_format, "%(street)s")
