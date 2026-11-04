from unittest.mock import patch

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestResCompany(TransactionCase):
    def test_default_company_stamp(self):
        stamp = self.env["res.company"]._default_company_stamp()
        self.assertTrue(stamp.content)

    def test_create_update_asset_style(self):
        Company = self.env["res.company"]
        with patch.object(type(Company), "_update_asset_style") as mock:
            company = Company.create({"name": "Plain Company"})
            mock.assert_not_called()
            Company.create({"name": "Styled Company", "tertiary_color": "#111111"})
            mock.assert_called_once()

            mock.reset_mock()
            company.write({"name": "Renamed"})
            mock.assert_not_called()
            company.write({"shading_option": "40"})
            mock.assert_called_once()
        self.assertEqual(company.font, "Sarabun")
