from datetime import date, datetime

from odoo import api, fields, models
from odoo.exceptions import ValidationError

from .report_table_column import get_path_field


class ReportDocumentLine(models.Model):
    _name = "report.document.line"
    _description = "Report Document Line"
    _order = "sequence"

    sequence = fields.Integer(
        default=10,
    )
    report_config_id = fields.Many2one(
        comodel_name="report.config",
        ondelete="cascade",
        index=True,
        copy=False,
    )
    model_id = fields.Many2one(
        related="report_config_id.model_id",
    )
    model = fields.Char(
        related="report_config_id.model",
    )
    name = fields.Char(
        string="Label",
        required=True,
        translate=True,
    )
    field_path = fields.Char(
        string="Field",
        help="Field of the document to print, e.g. 'name' or 'user_id.name' for the "
        "name of the salesperson.",
    )
    default_value = fields.Char(
        help="This value will be used in the report if the actual field value is empty",
    )
    is_label_bold = fields.Boolean(
        string="Label Bold",
        help="Enable to display the label in bold on the PDF report.",
    )
    is_value_bold = fields.Boolean(
        string="Value Bold",
        help="Enable to display the value in bold on the PDF report. "
        "Disable to use normal (regular) font weight.",
    )
    column_width = fields.Selection(
        selection=[
            ("1", "1"),
            ("2", "2"),
            ("3", "3"),
            ("4", "4"),
            ("5", "5"),
        ],
        default="4",
        required=True,
        help="Width of label's column",
    )

    @api.constrains("field_path", "report_config_id")
    def _check_field_path(self):
        for rec in self.filtered(lambda r: r.field_path and r.model):
            if not get_path_field(self.env, rec.model, rec.field_path):
                raise ValidationError(
                    self.env._(
                        "Document Details %(label)s: field %(path)s does not exist "
                        "on %(model)s.",
                        label=repr(rec.name),
                        path=repr(rec.field_path),
                        model=rec.model,
                    )
                )

    def _get_document_value(self, res_obj):
        """Value of the field path on `res_obj`: relations by name, dates in the
        report format, several values joined by commas. None when empty."""
        self.ensure_one()
        if not self.field_path:
            return None
        *relations, field_name = self.field_path.split(".")
        records = res_obj
        for relation in relations:
            records = records.mapped(relation)
        values = []
        for record in records.filtered(lambda r: field_name in r._fields):
            value = record[field_name]
            if isinstance(value, models.BaseModel):
                values.extend(value.mapped("display_name"))
            elif isinstance(value, datetime | date):
                values.append(self.report_config_id._get_report_date(res_obj, value))
            elif value or value == 0 and not isinstance(value, bool):
                values.append(value)
        if not values:
            return None
        return values[0] if len(values) == 1 else ", ".join(map(str, values))

    def _get_document_data(self, res_obj):
        self.ensure_one()
        value = self._get_document_value(res_obj)
        return {
            "key": self.name,
            "value": self.default_value if value is None else value,
            "col_w": f"col-{int(self.column_width)}",
        }

    def _prepare_document_vals(self, res_obj):
        self.ensure_one()
        res_obj.ensure_one()
        doc_data = self._get_document_data(res_obj)

        return {
            "key": doc_data.get("key"),
            "value": doc_data.get("value"),
            "label_bold": self.is_label_bold,
            "value_bold": self.is_value_bold,
            "col_w": doc_data.get("col_w"),
        }
