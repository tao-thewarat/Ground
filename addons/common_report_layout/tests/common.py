from odoo.tests import TransactionCase

MODULE = "common_report_layout"


class ReportLayoutCommon(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.is_ibase_layout = True
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Test Partner",
                "street": "1 Test Road",
                "city": "Bangkok",
                "lang": "en_US",
            }
        )
        cls._create_template(
            "test_report_document",
            '<t t-name="test_report_document"><span t-out="o.name"/></t>',
        )
        # Template setting a `lang` variable (e.g. invoices)
        cls.report_lang = cls._create_report(
            "test_report_lang",
            """
            <t t-name="test_report_lang">
                <t t-call="web.html_container">
                    <t t-foreach="docs" t-as="o">
                        <t t-set="lang" t-value="o.lang"/>
                        <span t-out="o.name"/>
                    </t>
                </t>
            </t>
            """,
        )
        # Template passing `t-lang` on the document call (e.g. sale orders)
        cls.report_t_lang = cls._create_report(
            "test_report_t_lang",
            f"""
            <t t-name="test_report_t_lang">
                <t t-call="web.html_container">
                    <t t-foreach="docs" t-as="o">
                        <t t-call="{MODULE}.test_report_document" t-lang="o.lang"/>
                    </t>
                </t>
            </t>
            """,
        )
        # Wrapper report only calling another report (e.g. invoice with payments)
        cls.report_wrapper = cls._create_report(
            "test_report_wrapper",
            f"""
            <t t-name="test_report_wrapper">
                <t t-call="{MODULE}.test_report_lang"/>
            </t>
            """,
        )
        cls.Config = cls.env["report.config"]
        cls.config = cls.Config.create(
            {
                "name": "Test Config",
                "action_report_id": cls.report_lang.id,
            }
        )

    @classmethod
    def _create_template(cls, name, arch):
        view = cls.env["ir.ui.view"].create(
            {
                "name": f"Template {name}",
                "type": "qweb",
                "key": f"{MODULE}.{name}",
                "arch_db": arch,
            }
        )
        cls.env["ir.model.data"].create(
            {
                "module": MODULE,
                "name": name,
                "model": "ir.ui.view",
                "res_id": view.id,
            }
        )
        return view

    @classmethod
    def _create_report(cls, name, arch, model="res.partner"):
        cls._create_template(name, arch)
        return cls.env["ir.actions.report"].create(
            {
                "name": f"Report {name}",
                "model": model,
                "report_type": "qweb-pdf",
                "report_name": f"{MODULE}.{name}",
            }
        )

    @classmethod
    def _get_field(cls, model, name):
        return cls.env["ir.model.fields"]._get(model, name)

    def _render_html(self, report):
        html, _ = self.env["ir.actions.report"]._render_qweb_html(
            report.report_name, self.partner.ids
        )
        return html.decode()
