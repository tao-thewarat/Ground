import re

from odoo import api, fields, models

from odoo.addons.base.models.ir_qweb_fields import nl2br


class ReportAddressLine(models.Model):
    _name = "report.address.line"
    _description = "Report Address Line"
    _order = "sequence"

    @api.model
    def _default_address_format(self):
        return self.env.company.country_id.address_format

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
    name = fields.Char(
        string="Label",
        required=True,
        translate=True,
    )
    field_id = fields.Many2one(
        comodel_name="ir.model.fields",
        domain="""[
            ('model_id', '=', model_id),
            ('ttype', '=', 'many2one'),
            ('relation', 'in', ('res.partner', 'res.company')),
        ]""",
        ondelete="set null",
    )
    address_format = fields.Text(
        string="Layout in Reports",
        default=lambda self: self._default_address_format(),
        help="Display format to use for addresses belonging to this country.\n\n"
        "You can use python-style string pattern with all the fields of the address "
        "(for example, use '%(street)s' to display the field 'street') plus"
        "\n%(state_name)s: the name of the state"
        "\n%(state_code)s: the code of the state"
        "\n%(country_name)s: the name of the country"
        "\n%(country_code)s: the code of the country",
    )
    is_custom_format = fields.Boolean(
        string="Custom Format",
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
    is_text_wrap = fields.Boolean(
        string="Text Wrap",
        default=True,
        help="Enable to allow long text to break onto the next line in the PDF report. "
        "Disable to keep text on line, which may cause it to overlap other content.",
    )
    column_width = fields.Selection(
        selection=[
            ("1", "1"),
            ("2", "2"),
            ("3", "3"),
            ("4", "4"),
            ("5", "5"),
        ],
        default="3",
        required=True,
        help="Width of label's column",
    )

    @api.model
    def _clean_report_address_format(
        self, address_format: str, company_data: dict
    ) -> str:
        """
        Clean up a formatted address string by removing unused placeholders.

        - Scans the address format string for placeholders (e.g., "%(city)s").
        - Removes any placeholders that don't exist in the provided `company_data` dict.
        - If a custom format is being used, removes additional placeholders not defined
        in the user's custom format (`self.address_format`).

        Args:
            address_format (str): The raw address format string containing placeholders.
            company_data (dict): Dictionary containing key-value pairs used to populate
                                 the format.

        Returns:
            str: The cleaned-up address format string, ready for rendering.

        Example:
            Input: "%(street)s\n%(city)s\n%(xyx)s",
                    company_data={"street": "123", "city": "Bangkok"}
            Output: "123\nBangkok"
        """
        self.ensure_one()
        # Pattern to find all placeholders like %(key)s
        pattern = re.compile(r"%\((\w+)\)s")
        keys_in_format = pattern.findall(address_format)

        # Step 1: Remove placeholders that are not present in company_data
        missing_keys = [key for key in keys_in_format if key not in company_data]
        for key in missing_keys:
            # Remove the line or just the placeholder
            address_format = re.sub(rf"%\({key}\)s\s*\n?", "", address_format)

        # Step 2: If custom format, also remove keys not present in self.address_format
        if self.is_custom_format and self.address_format:
            custom_keys = set(pattern.findall(self.address_format))
            keys_to_remove = [
                key for key in pattern.findall(address_format) if key not in custom_keys
            ]
            for key in keys_to_remove:
                address_format = re.sub(rf"%\({key}\)s\s*\n?", "", address_format)

        # Step 3: Remove any remaining broken % formats like trailing `%` or `%s`
        # without a key
        address_format = re.sub(r"%(?!\(\w+\)s)", "", address_format)
        return address_format

    def _get_report_address(self, res_obj):
        """
        Generate a display-ready address for a given record using a configurable format.

        - Retrieves the address format and data from the target model field.
        - Support using a custom address format if enabled (`is_custom_format` is True).
        - Cleans unused placeholders from the format before rendering.
        - Converts newlines to HTML `<br>` using `nl2br()` for display purposes.

        Args:
            res_obj (models.Model): The record to extract the res.partner.

        Returns:
            str: The HTML-ready, formatted address string.

        Example:
            If `res_obj` is a account.move and `field_id` is a partner_id with address:
                street = "123 ABC Rd.", city = "Bangkok"
            And custom format = "%(street)s\n%(city)s"
            The output will be:
                "123 ABC Rd.<br>Bangkok"
        """
        self.ensure_one()
        res_obj.ensure_one()
        is_custom_format = self.is_custom_format
        report_config = self.report_config_id
        partner = report_config._get_field_attr(res_obj, self.field_id.name)
        address_format, company_data = partner.with_context(
            custom_format=self.address_format if is_custom_format else None
        )._prepare_display_address()
        address_format = self._clean_report_address_format(address_format, company_data)
        return nl2br(address_format) % company_data

    def _prepare_address_vals(self, res_obj):
        self.ensure_one()
        res_obj.ensure_one()

        return {
            "key": self.name,
            "value": self._get_report_address(res_obj),
            "label_bold": self.is_label_bold,
            "value_bold": self.is_value_bold,
            "wrap": self.is_text_wrap,
            "col_w": f"col-{int(self.column_width)}",
        }
