try:
    import qrcode
except ImportError:  # pragma: no cover
    qrcode = None

import base64
import logging
import re
from datetime import date, datetime
from io import BytesIO
from xml.sax.saxutils import escape, quoteattr

from lxml import etree

from odoo import Command, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare, get_lang
from odoo.tools.safe_eval import safe_eval

from odoo.addons.common_readme.tools.date_tools import (
    extract_directives,
    get_date_only_directives,
    get_locale_date_format,
)

from .report_table_column import LINE_CODE_EXAMPLE

_logger = logging.getLogger(__name__)


class ReportSignatureLine(models.Model):
    _name = "report.config"
    _inherit = "report.mixin.tools"
    _description = "Reporting Configuration"
    _check_company_auto = True
    _rec_names_search = ["name", "model", "action_report_id", "layout_document_title"]

    @api.model
    def _default_time_format(self):
        user_lang = get_lang(self.env)
        return user_lang.time_format

    @api.model
    def _default_date_format(self):
        user_lang = get_lang(self.env)
        return user_lang.date_format

    name = fields.Char(
        string="Description",
        required=True,
    )
    model_id = fields.Many2one(
        related="action_report_id.model_id",
    )
    model = fields.Char(
        related="action_report_id.model",
    )
    action_report_id = fields.Many2one(
        comodel_name="ir.actions.report",
        string="Report",
        domain="[('report_type', '=', 'qweb-pdf'), ('paperformat_id', '=', False)]",
        copy=False,
        help="Filter a QWeb PDF report and without a paperformat only.",
    )
    lang_view_id = fields.Many2one(
        comodel_name="ir.ui.view",
        string="Dynamic Lang Template",
        ondelete="set null",
        help="The template inherit lang report from main report view.",
    )
    copy_view_id = fields.Many2one(
        comodel_name="ir.ui.view",
        string="Dynamic Copy Template",
        ondelete="set null",
        help="The template inherit foreach copy report from main report view.",
    )
    table_view_id = fields.Many2one(
        comodel_name="ir.ui.view",
        string="Dynamic Table Template",
        ondelete="set null",
        help="The template inherit replacing the items table of the report.",
    )
    totals_view_id = fields.Many2one(
        comodel_name="ir.ui.view",
        string="Dynamic Totals Template",
        ondelete="set null",
        help="The template inherit replacing the totals table of the report.",
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        default=lambda self: self.env.company,
    )
    layout_document_title = fields.Char(
        string="Document Title",
        translate=True,
    )
    address_line_ids = fields.One2many(
        comodel_name="report.address.line",
        inverse_name="report_config_id",
    )
    copy_line_ids = fields.One2many(
        comodel_name="report.copy.line",
        inverse_name="report_config_id",
    )
    document_line_ids = fields.One2many(
        comodel_name="report.document.line",
        inverse_name="report_config_id",
    )
    signature_line_ids = fields.One2many(
        comodel_name="report.signature.line",
        inverse_name="report_config_id",
    )
    session_width = fields.Selection(
        selection=[
            ("3", "Address 3 : Details 9"),
            ("4", "Address 4 : Details 8"),
            ("5", "Address 5 : Details 7"),
            ("6", "Address 6 : Details 6"),
            ("7", "Address 7 : Details 5"),
            ("8", "Address 8 : Details 4"),
            ("9", "Address 9 : Details 3"),
        ],
        default="6",
        required=True,
    )
    body_offset = fields.Float(
        string="Vertical Offset (mm)",
        digits=(16, 1),
        help="Move Address and Document Details up (negative) or down (positive). "
        "The items table below moves with them.",
    )
    body_gap = fields.Float(
        string="Gap Before Items (mm)",
        digits=(16, 1),
        help="Extra space between Address / Document Details and the items table. "
        "0 keeps the default spacing of the layout.",
    )
    qr_type = fields.Selection(
        selection=[
            ("portal", "QR Link to Portal"),
            ("doc_no", "Document No."),
            ("doc_link", "Document Link"),
        ],
    )
    signature_offset = fields.Float(
        string="Signature Vertical Offset (mm)",
        digits=(16, 1),
        help="Move all signature boxes up (negative) or down (positive). "
        "The page number stays in place.",
    )
    qr_label = fields.Char(
        string="QR Label",
        size=20,
        translate=True,
    )
    lang_code = fields.Char(
        string="Locale Code",
    )
    report_lang_options = fields.Selection(
        selection=[
            ("by_user", "User's Language"),
            ("by_report", "Report's Language"),
            ("fixed", "Fixed Language"),
        ],
        default="by_report",
        required=True,
    )
    format_options = fields.Selection(
        selection=[
            ("by_user", "User Format"),
            ("by_partner", "Partner Format"),
            ("custom", "Custom Format"),
        ],
        default="custom",
        required=True,
    )
    date_format = fields.Char(
        default=lambda self: self._default_date_format(),
    )
    time_format = fields.Char(
        default=lambda self: self._default_time_format(),
    )
    field_partner_format_id = fields.Many2one(
        comodel_name="ir.model.fields",
        string="Format by Partner",
        ondelete="set null",
    )
    origin_label = fields.Char(
        default="Original",
        translate=True,
    )
    copy_label = fields.Char(
        default="Copy",
        translate=True,
    )
    number_of_copies = fields.Integer(
        string="Number of Copies",
        help="Specify the number of copies to print for this document, "
        "The default is 1. any other number for additional copies.",
    )
    is_specific_title = fields.Boolean(
        string="Specific Title",
    )
    is_time_format = fields.Boolean(
        string="Show Time Format",
    )
    is_copy = fields.Boolean(
        string="Copy Document",
        help="Enable to Mark the document as a copy of the original.",
    )
    is_qr_code = fields.Boolean(
        string="QR Code",
        help="Enable to Display a QR code on the document.",
    )
    is_locale_date = fields.Boolean(
        string="Locale Date",
        help="Enable to Allow users to customize the date and time format, "
        "including the ability to use a custom date format (e.g., BE Year). "
        "When disabled, the system will use the default date format defined in the "
        "user's language settings.",
    )
    is_be_era = fields.Boolean(
        string="Buddhist Era",
        help="Enable to convert the year to the Buddhist Era (BE) format. "
        "This applies to year-related date fields.",
    )
    is_table_columns = fields.Boolean(
        string="Custom Table Columns",
        help="Replace the items table of the report with the columns below.",
    )
    is_row_number = fields.Boolean(
        string="Show Row Number",
        help="Add a first column numbering the printed lines 1, 2, 3... "
        "Sections and notes are not numbered.",
    )
    row_number_title = fields.Char(
        string="Row Number Column Title",
        default="No.",
        translate=True,
    )
    line_source = fields.Selection(
        selection=[
            ("field", "Field"),
            ("code", "Python Code"),
        ],
        default="field",
        required=True,
        help="Field: print the lines of a one2many field, optionally filtered.\n"
        "Python Code: compute the lines yourself (administrators only).",
    )
    line_field_id = fields.Many2one(
        comodel_name="ir.model.fields",
        domain="[('model_id', '=', model_id), "
        "('ttype', 'in', ('one2many', 'many2many'))]",
        ondelete="set null",
        help="Lines of the document, e.g. order_line or invoice_line_ids.",
    )
    line_domain = fields.Char(
        string="Line Filter",
        default="[]",
        help="Only the lines matching this domain are printed.",
    )
    line_model_id = fields.Many2one(
        comodel_name="ir.model",
        ondelete="set null",
        help="Model of the records returned by the Python code.",
    )
    line_code = fields.Text(
        string="Python Code",
        groups="base.group_system",
        help="Set `result` to the lines to print, a recordset of the Line Model.\n"
        "Available: doc (printed record), env.\n"
        "Example: result = doc.order_line.filtered(lambda l: l.product_uom_qty)",
    )
    line_model = fields.Char(
        compute="_compute_line_model",
    )
    table_column_ids = fields.One2many(
        comodel_name="report.table.column",
        inverse_name="report_config_id",
        string="Table Columns",
        copy=True,
    )
    table_total_width = fields.Float(
        string="Total Width",
        digits=(16, 1),
        compute="_compute_table_total_width",
    )
    is_totals = fields.Boolean(
        string="Custom Totals",
        help="Replace the totals below the items table with the lines below.",
    )
    total_line_ids = fields.One2many(
        comodel_name="report.total.line",
        inverse_name="report_config_id",
        string="Totals",
        copy=True,
    )

    @api.constrains("company_id", "action_report_id")
    def _check_unique_report_per_company(self):
        for rec in self:
            if not rec.company_id or not rec.action_report_id:
                continue

            existing = self.search(
                [
                    ("company_id", "=", rec.company_id.id),
                    ("action_report_id", "=", rec.action_report_id.id),
                    ("id", "!=", rec.id),
                ],
                limit=1,
            )

            if existing:
                raise ValidationError(
                    self.env._(
                        "Each report %(action_name)s can only be "
                        "configured once per company.",
                        action_name=repr(rec.action_report_id.name),
                    )
                )

    @api.constrains("body_gap")
    def _check_body_gap(self):
        if any(rec.body_gap < 0 for rec in self):
            raise ValidationError(self.env._("Gap Before Items cannot be negative."))

    @api.constrains("is_table_columns", "table_column_ids")
    def _check_table_total_width(self):
        for rec in self:
            if not rec.is_table_columns or not rec.table_column_ids:
                continue
            if float_compare(rec.table_total_width, 100.0, precision_digits=1):
                raise ValidationError(
                    self.env._(
                        "The visible table columns must be 100%% wide in total, "
                        "not %(total)s%%.",
                        total=rec.table_total_width,
                    )
                )

    @api.constrains("date_format")
    def _check_date_format(self):
        for rec in self:
            date_format = rec.date_format or ""
            # Validate: must only contain known directives and allowed separators
            allowed_directives = get_date_only_directives()
            extracted = extract_directives(date_format)
            if unknown_directives := extracted - allowed_directives:
                raise ValidationError(
                    self.env._(
                        "Date format contains invalid "
                        "directives: %(unknown_directives)s",
                        unknown_directives=unknown_directives,
                    )
                )

            # Check for any invalid characters (e.g., 'a' or 'x') outside directives
            # remove all directives
            cleaned = re.sub(r"%[a-zA-Z]", "", date_format)
            # remove allowed separators
            invalid_chars = re.sub(r"[-/.,: _]", "", cleaned)
            if invalid_chars:
                raise ValidationError(
                    self.env._(
                        "Date format must only contain valid directives and separators "
                        "(e.g. %%d/%%m/%%Y).\n"
                        "\t- Invalid characters found: %(invalid)s\n"
                        "\t- Allowed separators are:\n"
                        "\t\t' - '\t(Minus)\n"
                        "\t\t' / '\t(Slash)\n"
                        "\t\t' . '\t(Period/Dot)\n"
                        "\t\t' : '\t(Colon)\n"
                        "\t\t' , '\t(Comma)\n"
                        "\t\t' _ '\t(Underscore)\n"
                        "\t\t'   '\t(Space)"
                    )
                    % {"invalid": repr(invalid_chars)}
                )

    @api.depends("line_source", "line_field_id", "line_model_id")
    def _compute_line_model(self):
        for rec in self:
            rec.line_model = (
                rec.line_field_id.relation
                if rec.line_source == "field"
                else rec.line_model_id.model
            ) or False

    @api.depends("table_column_ids.width", "table_column_ids.is_visible")
    def _compute_table_total_width(self):
        for rec in self:
            rec.table_total_width = sum(
                rec.table_column_ids.filtered("is_visible").mapped("width")
            )

    @api.onchange("action_report_id")
    def _onchange_action_report_id(self):
        self.name = self.action_report_id.name

    @api.onchange("line_source", "line_model_id")
    def _onchange_line_source(self):
        """Start an empty Python code with a commented example."""
        if self.line_source == "code" and not self.line_code:
            self.update({"line_code": self._get_line_code_example()})

    @api.onchange("number_of_copies")
    def _onchange_number_of_copies(self):
        copy_line_vals_list = [Command.clear()]
        copy_line_vals_list.extend(
            [
                Command.create(
                    {
                        "doc_sequence": i,
                        "name": i == 1 and self.origin_label or self.copy_label,
                        "title_name": self.layout_document_title,
                        "copy_type": i == 1 and "main" or "copy",
                        "is_bold": True,
                    }
                )
                for i in range(1, self.number_of_copies + 2)
            ]
        )
        self.copy_line_ids = copy_line_vals_list

    def _update_copy_lang(self):
        valid_langs = {code for code, _ in self.env["res.lang"].get_installed()} | {
            "en_US"
        }

        for rec in self.copy_line_ids:
            for fn, fm in self._fields.items():
                if fn not in ("origin_label", "copy_label", "layout_document_title"):
                    continue

                if fn == "origin_label" and rec.copy_type != "main":
                    continue

                if fn == "copy_label" and rec.copy_type != "copy":
                    continue

                if fm.translate and fm.store:
                    old_stored_translations = fm._get_stored_translations(self)
                    if not old_stored_translations:
                        continue

                    update_field_name = (
                        "name" if fn != "layout_document_title" else "title_name"
                    )

                    if fm.translate is True:
                        rec.update_field_translations(
                            update_field_name,
                            {
                                k: v
                                for k, v in old_stored_translations.items()
                                if k in valid_langs
                            },
                        )

    def _get_extra_footer_template(self, res_obj):
        if hasattr(res_obj, "_get_extra_footer_template"):
            return res_obj._get_extra_footer_template(self)
        return False

    def _get_paperformat_by_config(self):
        self.ensure_one()
        formats = self.env.ref("common_report_layout.ibase_basic_paperformat")
        custom_format = self.env.ref("common_report_layout.ibase_custom_paperformat")
        margin_per_line = 5

        total_address_lines = [
            len(rec.address_format.splitlines()) for rec in self.address_line_ids
        ]
        header_factor_spacing = max(
            sum(total_address_lines),
            len(self.document_line_ids),
        )
        footer_factor_spacing = (
            4.5
            if self.signature_line_ids or (self.is_qr_code and self.qr_label)
            else (
                3.5
                if self.is_qr_code
                or any(rec.is_company_stamp for rec in self.signature_line_ids)
                else 0
            )
        )
        extra_footer_spacing = self.action_report_id.extra_footer_spacing
        header_spacing = margin_per_line * header_factor_spacing
        footer_spacing = margin_per_line * footer_factor_spacing + extra_footer_spacing

        header_spacing += self._get_body_spacing()

        custom_format.margin_top = formats.margin_top + header_spacing
        custom_format.margin_bottom = formats.margin_bottom + footer_spacing
        custom_format.margin_left = formats.margin_left
        custom_format.margin_right = formats.margin_right
        custom_format.header_spacing = round(formats.header_spacing + header_spacing)
        return custom_format

    def _get_body_spacing(self):
        """Space (mm) the body position adds above the items table."""
        self.ensure_one()
        return self.body_offset + self.body_gap

    def _get_body_style(self):
        """Inline style moving Address / Document Details inside the header."""
        self.ensure_one()
        return f"margin-top: {self.body_offset}mm; margin-bottom: {self.body_gap}mm;"

    def _get_signature_style(self):
        """Inline style moving the whole signature row inside the footer."""
        self.ensure_one()
        return f"position: relative; top: {self.signature_offset}mm;"

    def _get_line_code_example(self):
        """Commented Python code example, using the field of the report model that
        holds records of the Line Model when there is one."""
        self.ensure_one()
        line_model = self.line_model_id.model
        fields_map = self.env[self.model]._fields if self.model in self.env else {}
        line_field = next(
            (
                name
                for name, field in fields_map.items()
                if field.type == "one2many" and field.comodel_name == line_model
            ),
            "order_line",
        )
        model_note = f" ({line_model})" if line_model else ""
        return LINE_CODE_EXAMPLE.format(line_field=line_field, model_note=model_note)

    def _get_table_lines(self, doc):
        """Lines printed in the items table of `doc`, as a recordset of
        `line_model`."""
        self.ensure_one()
        lines = None
        if self.line_source == "code":
            local_vars = {"doc": doc, "env": doc.env, "result": None}
            safe_eval(self.sudo().line_code or "", local_vars, mode="exec")
            lines = local_vars["result"]
        elif self.line_field_id:
            lines = doc[self.line_field_id.name].filtered_domain(
                safe_eval(self.line_domain or "[]")
            )
            if "sequence" in lines._fields:  # document order
                lines = lines.sorted(lambda line: (line.sequence, line.id))
        if not isinstance(lines, models.BaseModel) or lines._name != self.line_model:
            raise UserError(
                self.env._(
                    "Configure Report %(name)s: the table lines must be records of "
                    "%(model)s.",
                    name=repr(self.name),
                    model=self.line_model or "?",
                )
            )
        return lines

    def _get_row_numbers(self, lines):
        """Row number of each line of `lines`, from 1 for each document, None for
        sections and notes."""
        numbers = []
        count = 0
        for line in lines:
            if "display_type" in line._fields and line.display_type in (
                "line_section",
                "line_subsection",
                "line_note",
            ):
                numbers.append(None)
                continue
            count += 1
            numbers.append(count)
        return numbers

    def _get_table_line_label(self, line):
        """Text of a section or note line."""
        return line["name"] if "name" in line._fields else line.display_name

    def _find_table_view(self, view, css_class="o_main_table", depth=0):
        """View holding the table with `css_class` (the items table by default) of
        the report, following the templates the report calls."""
        arch = etree.fromstring(view.arch_db or "<t/>")
        if arch.xpath(f"//table[contains(concat(' ', @class, ' '), ' {css_class} ')]"):
            return view
        if depth >= 3:
            return self.env["ir.ui.view"]
        for ref in arch.xpath("//t/@t-call"):
            if ref.startswith("web.") or "{" in ref:
                continue
            child = self.env.ref(ref, raise_if_not_found=False)
            if child and child._name == "ir.ui.view":
                found = self._find_table_view(child, css_class, depth + 1)
                if found:
                    return found
        return self.env["ir.ui.view"]

    def _get_table_arch_db(self, table_view):
        table = "//table[hasclass('o_main_table')]"
        return f"""
            <data inherit_id="{table_view.key}">
                <xpath expr="{table}" position="before">
                    <t t-set="ibase_table_config"
                    t-value="docs and docs._context.get('report_config')"/>
                    <t t-set="table_doc" t-value="o or doc"/>
                    <t t-if="ibase_table_config and ibase_table_config.is_table_columns"
                    t-call="common_report_layout.ibase_table_columns"/>
                    <t t-else="" name="ibase_core_table"/>
                </xpath>
                <xpath expr="//t[@name='ibase_core_table']" position="inside">
                    <xpath expr="{table}" position="move"/>
                </xpath>
            </data>
        """  # noqa: B907

    def _get_totals_arch_db(self, totals_view):
        table = "//table[hasclass('o_total_table')]"
        return f"""
            <data inherit_id="{totals_view.key}">
                <xpath expr="{table}" position="before">
                    <t t-set="ibase_totals_config"
                    t-value="docs and docs._context.get('report_config')"/>
                    <t t-set="totals_doc" t-value="o or doc"/>
                    <t t-if="ibase_totals_config and ibase_totals_config.is_totals"
                    t-call="common_report_layout.ibase_totals"/>
                    <t t-else="" name="ibase_core_totals"/>
                </xpath>
                <xpath expr="//t[@name='ibase_core_totals']" position="inside">
                    <xpath expr="{table}" position="move"/>
                </xpath>
            </data>
        """  # noqa: B907

    def _update_inherit_view(
        self, view_field, is_enabled, css_class, get_arch_db, error_message
    ):
        """Create, update or remove the view of `view_field` replacing the table
        with `css_class` of the report, `error_message` when it has none."""
        self.ensure_one()
        if not is_enabled or not self.action_report_id:
            self[view_field].sudo().unlink()
            return
        report_view = self.env.ref(self.action_report_id.report_name)
        target_view = self._find_table_view(report_view, css_class)
        if not target_view:
            raise UserError(error_message)
        vals = {
            "inherit_id": target_view.id,
            "arch_db": get_arch_db(target_view),
        }
        if self[view_field]:
            self[view_field].sudo().write(vals)
            return
        suffix = view_field.removesuffix("_view_id")
        view = (
            self.env["ir.ui.view"]
            .sudo()
            .create(
                {
                    **vals,
                    "name": f"{target_view.name}_{suffix}_config",
                    "mode": "extension",
                    "type": "qweb",
                    "key": f"common_report_layout.{target_view.key}_{suffix}_{self.id}",
                }
            )
        )
        self.write({view_field: view.id})

    def _update_table_view(self):
        self._update_inherit_view(
            "table_view_id",
            self.is_table_columns,
            "o_main_table",
            self._get_table_arch_db,
            self.env._(
                "The items table of report %(report)s cannot be found.",
                report=repr(self.action_report_id.name),
            ),
        )

    def _update_totals_view(self):
        self._update_inherit_view(
            "totals_view_id",
            self.is_totals,
            "o_total_table",
            self._get_totals_arch_db,
            self.env._(
                "The totals table of report %(report)s cannot be found.",
                report=repr(self.action_report_id.name),
            ),
        )

    def _get_totals_currency(self, doc):
        """Currency the totals of `doc` are printed in."""
        self.ensure_one()
        currency = self.env["report.total.line"]._get_doc_value(doc, "currency_id")
        return currency or self.company_id.currency_id or self.env.company.currency_id

    def _get_total_rows(self, doc):
        """Rows of the totals table of `doc`, from the visible total lines."""
        self.ensure_one()
        currency = self._get_totals_currency(doc)
        return [
            row
            for line in self.total_line_ids.filtered("is_visible")
            for row in line._get_rows(doc, currency)
        ]

    def _get_field_attr(self, res_obj, field_name: str):
        """
        Returns the value of a field (by name) from a given record object.

        Parameters:
        - res_obj (record set): The record from which to retrieve the field value.
        - field_name (str): The technical name of the field to retrieve.

        Returns:
        - The value of the field if both the record and field name are valid.
        - None if either the record or the field name is missing.

        Examples:
            # Single record
                user = self.env['res.users'].browse(3)
                email = self._get_field_attr(user, 'email')

                Returns: 'user@example.com'

            # Multiple records
                journals = self.env['account.journal'].browse([8, 15])
                names = self._get_field_attr(journals, 'display_name')

                Returns: 'Bank, Cash'
        """
        if not res_obj or not field_name:
            return None

        if len(res_obj) > 1:
            return ", ".join(res_obj.mapped(field_name))
        return getattr(res_obj, field_name, None)

    def _get_report_date(
        self, res_obj, dt: date | datetime, strict: bool = False
    ) -> str:
        """
        Format a date or datetime based on configuration options set in the record.

        - Determines the date format and locale based on one of the following:
            - Current user's language (`by_user`)
            - Partner's language (`by_partner`)
            - Custom format (`custom`)
        - Optionally includes time format if the input is a datetime and time formatting
          is enabled.
        - Optionally applies Buddhist Era year conversion.

        Args:
            res_obj (models.Model): The record whose partner or
                                    context may determine the lang.
            dt (date | datetime): The date or datetime to be formatted.
            strict (bool, optional): If True, skip time formatting.

        Returns:
            str: The formatted date string.
        """
        self.ensure_one()
        Lang = self.env["res.lang"]
        be_year = self.is_be_era and self.is_locale_date
        py_format = None
        iso_code = None

        if not self.is_locale_date:
            pass
        elif self.format_options == "by_user":
            user_lang = get_lang(self.env, self.env.user.lang)
            py_format = user_lang.date_format
            iso_code = user_lang.iso_code
        elif self.format_options == "by_partner":
            partner_id = getattr(res_obj, self.field_partner_format_id.name)
            partner_lang = hasattr(partner_id, "lang") and Lang._lang_get(
                code=partner_id.lang
            )
            if partner_lang:
                py_format = partner_lang.date_format
                iso_code = partner_lang.iso_code
        elif self.format_options == "custom":
            py_format = self.date_format

        if isinstance(dt, datetime) and self.is_time_format and not strict:
            py_format += " " + self.time_format

        return get_locale_date_format(self.env, dt, py_format, be_year, iso_code)

    def _get_record_url(self, record):
        """Portal link with the access token, so the customer opens the document
        without an account. Models without a portal page get the backend link."""
        if not record or not record.exists():
            return None
        if hasattr(record, "get_portal_url"):
            return f"{record.get_base_url()}{record.sudo().get_portal_url()}"
        return self._get_backend_url(record)

    def _get_backend_url(self, record):
        """Backend link of the record, e.g. /odoo/sales/7 (internal users log in).
        Uses the menu action of the document when the model defines one, else the
        model name, which Odoo also opens."""
        if not record or not record.exists():
            return None
        path = record._name
        if hasattr(record, "_get_portal_return_action"):
            path = record._get_portal_return_action().path or path
        return f"{record.get_base_url()}/odoo/{path}/{record.id}"

    def _get_date_qr_code(self, res_obj):
        self.ensure_one()
        data = ""
        if self.qr_type == "doc_no":
            data = res_obj.display_name
        elif self.qr_type == "portal":
            data = self._get_record_url(res_obj)
        elif self.qr_type == "doc_link":
            data = self._get_backend_url(res_obj)
        return data

    def generate_qr_config(self, res_obj):
        self.ensure_one()
        if qrcode:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=0,
            )

            data = self._get_date_qr_code(res_obj)
            qr.add_data(data)
            qr.make(fit=True)
            img = qr.make_image()
            temp = BytesIO()
            img.save(temp, "PNG")
            qr_image = base64.b64encode(temp.getvalue())
            return qr_image
        raise UserError(
            self.env._("Necessary Requirements To Run This Operation Is Not Satisfied")
        )

    def _get_copy_label_list(self):
        return [rec._prepare_copy_vals() for rec in self.copy_line_ids]

    def get_report_address_vals_list(self, res_obj):
        self.ensure_one()
        res_obj.ensure_one()
        return [rec._prepare_address_vals(res_obj) for rec in self.address_line_ids]

    def get_report_document_vals_list(self, res_obj):
        self.ensure_one()
        res_obj.ensure_one()
        return [rec._prepare_document_vals(res_obj) for rec in self.document_line_ids]

    def get_report_signature_vals_list(self, res_obj):
        self.ensure_one()
        res_obj.ensure_one()
        return [rec._prepare_signature_vals(res_obj) for rec in self.signature_line_ids]

    def _get_lang_value(self, current):
        """QWeb expression of the report language, `current` being the template's."""
        if self.report_lang_options == "by_user":
            return f"user.lang or ({current})"
        if self.report_lang_options == "fixed":
            return f"{self.lang_code!r} or ({current})"
        return current

    def _get_lang_arch_db(self, report_view, report_template_ref):
        """Inheritance setting the report language. Templates either set a `lang`
        variable (invoices) or pass `t-lang` on the document call (Odoo 20 sale
        orders). Wrapper reports that only call another report have neither: None."""
        arch = etree.fromstring(report_view.arch_db or "<t/>")
        if arch.xpath("//t[@t-set='lang']"):
            lang_value = quoteattr(self._get_lang_value("lang"))
            return f"""
                <data inherit_id="{report_template_ref}">
                    <xpath expr="//t[@t-set='lang']" position="after">
                        <t t-set="lang" t-value={lang_value}/>
                    </xpath>
                </data>
            """
        t_lang = arch.xpath("//t[@t-lang]")
        if t_lang:
            value = self._get_lang_value(t_lang[0].get("t-lang"))
            return f"""
                <data inherit_id="{report_template_ref}">
                    <xpath expr="//t[@t-lang]" position="attributes">
                        <attribute name="t-lang">{escape(value)}</attribute>
                    </xpath>
                </data>
            """
        return None

    def _update_lang_view(self, report_view, report_template_ref):
        arch_db = self._get_lang_arch_db(report_view, report_template_ref)
        if not arch_db:
            self.lang_view_id.sudo().unlink()
            return
        if not self.lang_view_id:
            view = self.env["ir.ui.view"].create(
                {
                    "name": f"{report_view.name}_language_config",
                    "mode": "extension",
                    "type": "qweb",
                    "inherit_id": report_view.id,
                    "key": f"common_report_layout.{report_view.name}",
                    "arch_db": arch_db,
                }
            )
            self.lang_view_id = view.id
        else:
            self.lang_view_id.write({"arch_db": arch_db})

    def _get_copy_target_xpath(self, report_view):
        """Node repeated for each copy: the html container, or the template call of
        wrapper reports that only call another report (e.g. invoice with payments)."""
        if "web.html_container" in (report_view.arch_db or ""):
            return "//t[@t-call='web.html_container']"
        return "/t/t[@t-call]"

    def _get_copy_arch_db(self, report_view, report_template_ref):
        self.ensure_one()
        target = self._get_copy_target_xpath(report_view)
        return f"""
            <data inherit_id="{report_template_ref}">
                <xpath expr="{target}" position="before">
                    <t t-foreach="range(1, {self.number_of_copies + 2})"
                    t-as="copy_count" name="foreach_copy"/>
                </xpath>
                <xpath expr="//t[@name='foreach_copy']" position="inside">
                    <xpath expr="{target}" position="move"/>
                </xpath>
            </data>
        """  # noqa: B907

    def _update_copy_view(self, report_view, report_template_ref):
        self.ensure_one()
        if self.copy_view_id and not self.is_copy:
            self.copy_view_id.sudo().unlink()

        if self.is_copy:
            arch_db = self._get_copy_arch_db(report_view, report_template_ref)
            if not self.copy_view_id:
                view = self.env["ir.ui.view"].create(
                    {
                        "name": f"{report_view.name}_copy_config",
                        "mode": "extension",
                        "type": "qweb",
                        "inherit_id": report_view.id,
                        "key": f"common_report_layout.{report_view.name}",
                        "arch_db": arch_db,
                    }
                )
                self.copy_view_id = view.id
            else:
                self.copy_view_id.write({"arch_db": arch_db})

    def button_body_offset_up(self):
        self.body_offset -= 1

    def button_body_offset_down(self):
        self.body_offset += 1

    def button_body_gap_decrease(self):
        self.body_gap = max(self.body_gap - 1, 0.0)

    def button_body_gap_increase(self):
        self.body_gap += 1

    def button_body_offset_reset(self):
        self.body_offset = 0.0

    def button_body_gap_reset(self):
        self.body_gap = 0.0

    def button_signature_offset_up(self):
        self.signature_offset -= 1

    def button_signature_offset_down(self):
        self.signature_offset += 1

    def button_signature_offset_reset(self):
        self.signature_offset = 0.0

    def button_load_default_columns(self):
        """Replace the columns with the usual columns of the line model."""
        self.ensure_one()
        columns = self.env["report.table.column"]._get_default_vals_list(
            self.line_model
        )
        self.write(
            {
                "table_column_ids": [Command.clear()]
                + [Command.create(v) for v in columns]
            }
        )

    def button_load_default_totals(self):
        """Replace the totals with the usual totals of the report model."""
        self.ensure_one()
        lines = self.env["report.total.line"]._get_default_vals_list(self.model)
        self.write(
            {"total_line_ids": [Command.clear()] + [Command.create(v) for v in lines]}
        )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records.filtered("is_table_columns"):
            rec._update_table_view()
        for rec in records.filtered("is_totals"):
            rec._update_totals_view()
        return records

    def write(self, vals):
        if self:
            self.ensure_one()

        old_action_report = self.env["ir.actions.report"]
        if vals.get("action_report_id"):
            old_action_report = self.action_report_id

        res = super().write(vals)

        if (
            vals.get("origin_label")
            or vals.get("copy_label")
            or vals.get("layout_document_title")
        ):
            self._update_copy_lang()

        if vals.get("action_report_id") and old_action_report != self.action_report_id:
            self.lang_view_id.sudo().unlink()
            self.copy_view_id.sudo().unlink()
            self.table_view_id.sudo().unlink()
            self.totals_view_id.sudo().unlink()

        if "is_table_columns" in vals or vals.get("action_report_id"):
            self._update_table_view()

        if "is_totals" in vals or vals.get("action_report_id"):
            self._update_totals_view()

        if (
            vals.get("action_report_id")
            or vals.get("report_lang_options")
            or vals.get("lang_code")
            or "is_copy" in vals
            or "number_of_copies" in vals
        ):
            report_template_ref = self.action_report_id.report_name
            report_view = self.env.ref(report_template_ref)

            if report_view and (
                vals.get("report_lang_options") or vals.get("lang_code")
            ):
                try:
                    self._update_lang_view(report_view, report_template_ref)
                except (UserError, ValidationError):
                    _logger.error(
                        "An error occurred in write: _update_lang_view"
                        " - cannot be located in parent view"
                    )

            if report_view and ("is_copy" in vals or "number_of_copies" in vals):
                try:
                    self._update_copy_view(report_view, report_template_ref)
                except (UserError, ValidationError):
                    _logger.error(
                        "An error occurred in write: _update_copy_view"
                        " - cannot be located in parent view"
                    )

        return res
