from types import SimpleNamespace

from lxml import etree

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestReportMixin(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Mixin = cls.env["report.mixin"]

    def test_get_view_form_adds_report_page(self):
        view = self.env["ir.ui.view"].create(
            {
                "name": "Test Report Mixin Form",
                "model": "report.mixin",
                "type": "form",
                "arch": """
                    <form>
                        <notebook>
                            <page name="main" string="Main"/>
                        </notebook>
                    </form>
                """,
            }
        )
        res = self.Mixin.get_view(view.id, "form")
        doc = etree.fromstring(res["arch"])
        pages = doc.xpath("//notebook/page")
        self.assertEqual(pages[-1].get("name"), "mixin_report_page")
        self.assertTrue(doc.xpath("//field[@name='is_show_discount']"))

    def test_get_view_other_type(self):
        view = self.env["ir.ui.view"].create(
            {
                "name": "Test Report Mixin List",
                "model": "report.mixin",
                "type": "list",
                "arch": '<list><field name="is_show_discount"/></list>',
            }
        )
        res = self.Mixin.get_view(view.id, "list")
        self.assertNotIn(
            b"mixin_report_page", etree.tostring(etree.fromstring(res["arch"]))
        )

    def _compute(self, method, description, code):
        # report.mixin is abstract: run the compute on a plain record-like object
        rec = SimpleNamespace(
            is_show_product_description=description, is_show_product_code=code
        )
        getattr(type(self.Mixin), method)([rec])
        return rec

    def test_compute_is_show_product_description(self):
        method = "_compute_is_show_product_description"
        self.assertFalse(self._compute(method, True, False).is_show_product_description)
        self.assertTrue(self._compute(method, True, True).is_show_product_description)

    def test_compute_is_show_product_code(self):
        method = "_compute_is_show_product_code"
        self.assertTrue(self._compute(method, True, False).is_show_product_code)
        self.assertTrue(self._compute(method, False, True).is_show_product_code)
