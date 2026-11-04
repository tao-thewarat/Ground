from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestResConfigSettings(TransactionCase):
    def test_is_ibase_layout(self):
        self.env.company.is_ibase_layout = True
        settings = self.env["res.config.settings"].create({})
        self.assertTrue(settings.is_ibase_layout)
