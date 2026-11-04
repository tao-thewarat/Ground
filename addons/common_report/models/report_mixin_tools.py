from datetime import date, datetime

from odoo import api, models

from odoo.addons.common_readme.tools.date_tools import get_locale_date_format


class ReportToolsMixin(models.AbstractModel):
    _name = "report.mixin.tools"
    _description = "Report Tools Mixin"

    @api.model
    def get_report_locale_date(
        self,
        dt: date | datetime,
        py_format: str = "",
        be_year: bool = False,
        iso_code: str = "",
    ) -> str:
        return get_locale_date_format(self.env, dt, py_format, be_year, iso_code)

    @api.model
    def _get_partner_legend(self, partner, legend: str) -> str:
        _, args = partner._prepare_display_address(without_name=False)
        return args.get(legend) or ""
