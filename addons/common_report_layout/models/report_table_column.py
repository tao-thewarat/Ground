from markupsafe import Markup, escape

from odoo import api, fields, models
from odoo.exceptions import ValidationError

# (label, candidate field paths, width %, alignment): the first path that exists
# on the line model is used, the column is skipped when none does
DEFAULT_TABLE_COLUMNS = [
    ("Description", ("label", "name"), 40.0, "left"),
    ("Quantity", ("quantity", "product_qty", "product_uom_qty"), 12.0, "right"),
    ("Unit Price", ("price_unit",), 16.0, "right"),
    ("Taxes", ("tax_ids",), 12.0, "right"),
    ("Amount", ("price_subtotal",), 20.0, "right"),
]

LINE_CODE_EXAMPLE = """# Lines printed in the items table.
# Available variables:
#   doc: the printed record, e.g. the invoice or the order
#   env: the Odoo environment
# Set `result` to records of the Line Model{model_note},
# in the order to print them.
#
# Examples:
#   Skip notes:
#     result = doc.{line_field}.filtered(lambda line: line.display_type != "line_note")
#   Only lines with an amount, sections kept:
#     result = doc.{line_field}.filtered(
#         lambda line: line.display_type or line.price_subtotal
#     )
#   Sort by product code:
#     result = doc.{line_field}.sorted(lambda line: line.product_id.default_code or "")
result = doc.{line_field}
"""


def get_path_field(env, model_name, path):
    """Field a dotted path ends on, following relations, None when invalid."""
    field = None
    for part in (path or "").split("."):
        if field is not None:
            if not field.relational:
                return None
            model_name = field.comodel_name
        field = env[model_name]._fields.get(part) if model_name in env else None
        if field is None:
            return None
    return field


ALIGNMENT_CLASSES = {
    "left": "text-start",
    "center": "text-center",
    "right": "text-end",
}


class ReportTableColumn(models.Model):
    _name = "report.table.column"
    _description = "Report Table Column"
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
    line_model = fields.Char(
        related="report_config_id.line_model",
    )
    name = fields.Char(
        string="Label",
        required=True,
        translate=True,
    )
    field_path = fields.Char(
        string="Field",
        required=True,
        help="Field of the line to print, e.g. 'name' or "
        "'product_id.default_code' for the product's Internal Reference.",
    )
    width = fields.Float(
        string="Width (%)",
        digits=(16, 1),
        default=10.0,
    )
    header_alignment = fields.Selection(
        selection=[
            ("left", "Left"),
            ("center", "Center"),
            ("right", "Right"),
        ],
        default="left",
        required=True,
        help="Alignment of the column header.",
    )
    alignment = fields.Selection(
        selection=[
            ("left", "Left"),
            ("center", "Center"),
            ("right", "Right"),
        ],
        string="Value Alignment",
        default="left",
        required=True,
        help="Alignment of the values in the column.",
    )
    default_value = fields.Char(
        translate=True,
        help="Printed when the line has no value for this column, e.g. '-'.",
    )
    is_text_wrap = fields.Boolean(
        string="Text Wrap",
        default=True,
    )
    is_visible = fields.Boolean(
        string="Visible",
        default=True,
    )

    @api.constrains("field_path", "report_config_id")
    def _check_field_path(self):
        for rec in self:
            if rec.line_model and not get_path_field(
                self.env, rec.line_model, rec.field_path
            ):
                raise ValidationError(
                    self.env._(
                        "Column %(label)s: field %(path)s does not exist on %(model)s.",
                        label=repr(rec.name),
                        path=repr(rec.field_path),
                        model=rec.line_model,
                    )
                )

    @api.model
    def _get_default_vals_list(self, line_model):
        """Values of the usual columns of `line_model`, 100% wide in total."""
        line_fields = self.env[line_model]._fields if line_model else {}
        presets = [
            [label, path, width, alignment]
            for label, paths, width, alignment in DEFAULT_TABLE_COLUMNS
            for path in [next((p for p in paths if p in line_fields), None)]
            if path
        ]
        if presets:  # the first column takes what the skipped ones leave
            presets[0][2] += 100.0 - sum(preset[2] for preset in presets)
        return [
            {
                "sequence": sequence,
                "name": label,
                "field_path": path,
                "width": width,
                "header_alignment": alignment,
                "alignment": alignment,
            }
            for sequence, (label, path, width, alignment) in enumerate(presets)
        ]

    def _get_css_class(self, header=False):
        """Classes of the header cell (header=True) or of the value cells."""
        self.ensure_one()
        alignment = self.header_alignment if header else self.alignment
        wrap = "" if self.is_text_wrap else " text-nowrap"
        return ALIGNMENT_CLASSES[alignment] + wrap

    def _format_value(self, record, field_name):
        """HTML of one record's field, formatted like `t-field`. Empty: ''."""
        field = record._fields[field_name]
        if field.type == "boolean":
            return "✓" if record[field_name] else ""
        if (
            field.type not in ("integer", "float", "monetary")
            and not record[field_name]
        ):
            return ""
        converter = self.env.get(
            f"ir.qweb.field.{field.type}", self.env["ir.qweb.field"]
        )
        return converter.record_to_html(record, field_name, {}) or ""

    def _get_display_value(self, line):
        """Formatted value of the column for one line, the Default Value when
        there is none."""
        self.ensure_one()
        *relations, field_name = self.field_path.split(".")
        records = line
        for relation in relations:
            records = records.mapped(relation)
        values = [self._format_value(record, field_name) for record in records]
        value = Markup(", ").join(escape(value) for value in values if value)
        return value or self.default_value or ""
