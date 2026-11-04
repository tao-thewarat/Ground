from odoo import api, fields, models
from odoo.exceptions import ValidationError

# (label, source, field name, bold, hide when zero): a line is skipped when the
# report model has no such field, or no tax totals / payments for those sources
DEFAULT_TOTAL_LINES = [
    ("Untaxed Amount", "field", "amount_untaxed", False, False),
    ("Taxes", "tax", "tax_totals", False, True),
    ("Total", "field", "amount_total", True, False),
    ("Payments", "payment", "invoice_payments_widget", False, True),
    ("Amount Due", "field", "amount_residual", True, False),
]

AMOUNT_FIELD_TYPES = ("monetary", "float", "integer")


class ReportTotalLine(models.Model):
    _name = "report.total.line"
    _description = "Report Total Line"
    _order = "sequence, id"

    sequence = fields.Integer(
        default=10,
    )
    report_config_id = fields.Many2one(
        comodel_name="report.config",
        ondelete="cascade",
        index=True,
        required=True,
    )
    model = fields.Char(
        related="report_config_id.model",
    )
    name = fields.Char(
        string="Label",
        required=True,
        translate=True,
    )
    source = fields.Selection(
        selection=[
            ("field", "Document Field"),
            ("tax", "Tax Summary"),
            ("payment", "Payments"),
        ],
        default="field",
        required=True,
        help="Document Field: an amount of the document, e.g. Untaxed Amount.\n"
        "Tax Summary: one line per tax group, e.g. VAT 7%.\n"
        "Payments: one line per payment reconciled with the invoice.",
    )
    field_id = fields.Many2one(
        comodel_name="ir.model.fields",
        domain="[('model_id.model', '=', model), "
        "('ttype', 'in', ('monetary', 'float', 'integer'))]",
        ondelete="cascade",
        help="Amount field of the document, custom fields included.",
    )
    is_bold = fields.Boolean(
        string="Bold",
    )
    is_visible = fields.Boolean(
        string="Visible",
        default=True,
    )
    is_hide_zero = fields.Boolean(
        string="Hide When Zero",
    )

    @api.constrains("source", "field_id")
    def _check_field_id(self):
        for rec in self:
            if rec.source == "field" and rec.field_id.ttype not in AMOUNT_FIELD_TYPES:
                raise ValidationError(
                    self.env._(
                        "Total %(label)s: choose an amount field of the document.",
                        label=repr(rec.name),
                    )
                )

    @api.model
    def _get_default_vals_list(self, model):
        """Values of the usual totals of `model`, those it supports."""
        Fields = self.env["ir.model.fields"]
        vals_list = []
        for label, source, field_name, bold, hide_zero in DEFAULT_TOTAL_LINES:
            field = Fields._get(model, field_name) if model else Fields
            if not field:
                continue
            vals_list.append(
                {
                    "sequence": len(vals_list),
                    "name": label,
                    "source": source,
                    "field_id": field.id if source == "field" else False,
                    "is_bold": bold,
                    "is_hide_zero": hide_zero,
                }
            )
        return vals_list

    @api.model
    def _get_doc_value(self, doc, field_name):
        """Value of `field_name` on `doc`, None when the model has no such field."""
        return doc[field_name] if field_name in doc._fields else None

    def _get_rows(self, doc, currency):
        """Rows this line prints for `doc`: label, amount, bold, and for payments
        their date and whether they are refunds."""
        self.ensure_one()
        if self.source == "field":
            name = self.field_id.name
            rows = [
                {"label": self.name, "amount": self._get_doc_value(doc, name) or 0.0}
            ]
        elif self.source == "tax":
            tax_totals = self._get_doc_value(doc, "tax_totals")
            rows = [
                {"label": group["group_name"], "amount": group["tax_amount_currency"]}
                for subtotal in (tax_totals or {}).get("subtotals", [])
                for group in subtotal["tax_groups"]
            ]
        else:
            # reconciled payments only, outstanding credits are not deducted
            widget = self._get_doc_value(doc.sudo(), "invoice_payments_widget")
            rows = [
                {
                    "label": self.name,
                    "amount": payment["amount"],
                    "date": payment["date"],
                    "is_refund": payment["is_refund"],
                }
                for payment in (widget or {}).get("content", [])
                if not payment["is_exchange"]
            ]
        if self.is_hide_zero:
            rows = [row for row in rows if not currency.is_zero(row["amount"])]
        for row in rows:
            row.update(type=self.source, bold=self.is_bold)
        return rows
