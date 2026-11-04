from lxml import etree

from odoo import api, fields, models
from odoo.tools.misc import frozendict


class ReportMixin(models.AbstractModel):
    _name = "report.mixin"
    _inherit = ["report.mixin.tools"]
    _description = "Report Mixin"

    is_show_discount = fields.Boolean(
        default=True,
    )
    is_show_product_description = fields.Boolean(
        compute="_compute_is_show_product_description",
        store=True,
        readonly=False,
    )
    is_show_product_code = fields.Boolean(
        compute="_compute_is_show_product_code",
        store=True,
        readonly=False,
    )

    @api.model
    def get_view(self, view_id=None, view_type="form", **options):
        res = super().get_view(view_id=view_id, view_type=view_type, **options)
        View = self.env["ir.ui.view"]
        if view_type == "form":
            doc = etree.XML(res["arch"])
            params = {}
            all_models = res["models"].copy()
            for node in doc.xpath("//notebook/page[last()]"):
                new_node = self._add_page_report_condition(node, params)
                new_arch, _ = View.postprocess_and_fields(new_node, self._name)
                new_node = etree.fromstring(new_arch)
                for new_element in new_node:
                    node.addnext(new_element)

            res["arch"] = etree.tostring(doc)
            res["models"] = frozendict(all_models)
        return res

    def _add_page_report_condition(self, _node, params):
        str_element = self.env["ir.qweb"]._render(
            "common_report.document_report_condition", params
        )
        new_node = etree.fromstring(str_element)
        return new_node

    @api.depends("is_show_product_code")
    def _compute_is_show_product_description(self):
        for rec in self:
            if rec.is_show_product_description and not rec.is_show_product_code:
                rec.is_show_product_description = False

    @api.depends("is_show_product_description")
    def _compute_is_show_product_code(self):
        for rec in self:
            if rec.is_show_product_description:
                rec.is_show_product_code = rec.is_show_product_description
