###################################################################################
#
#    Copyright (C) 2020 Cetmix OÜ
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU LESSER GENERAL PUBLIC LICENSE as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU LESSER GENERAL PUBLIC LICENSE for more details.
#
#    You should have received a copy of the GNU LESSER GENERAL PUBLIC LICENSE
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
###################################################################################

import json
import logging
import re

import werkzeug.exceptions
from werkzeug.urls import url_parse

from odoo.http import request, route
from odoo.http.dispatcher import serialize_exception
from odoo.http.stream import content_disposition
from odoo.tools.misc import html_escape
from odoo.tools.safe_eval import safe_eval
from odoo.tools.safe_eval import time as safe_time

from odoo.addons.web.controllers.report import ReportController

_logger = logging.getLogger(__name__)


class CxReportController(ReportController):
    def _get_extra_context_for_single_record(self, report_name, ignore_expr=None):
        """
        Get extra context values for single record report name
        evaluation. This is used to fill missing expressions with
        'report' string to avoid evaluation errors.

        Args:
        report_name (str): Name of the report.
            Example:
            "(object.state in ('draft', 'sent') and 'Quotation - %s' % (object.name))
            or 'Order - %s' % (object.name)"
        ignore_expr (list): List of expressions to ignore.

        Returns:
            Dict: Extra context values
        """
        ignore_expr = ignore_expr or []
        extra_ctx = {}
        for expr in re.findall(r"%.?\(.*?\)", report_name):
            # Remove percent sign and brackets, we don't need them
            expr = expr.replace("%", "").strip()[1:-1].strip()
            # If there is a dot in expression, then lets take
            # first part to get the variable name
            if "." in expr:
                expr = expr.split(".")[0]
            if expr in ignore_expr:
                continue
            extra_ctx[expr] = "report"
        return extra_ctx

    def _compose_report_file_name(self, docids, report):
        """Compose report file name.
        Uses report name + record name(s) if provided

        Args:
            docids ([Int]): list of record ids
            report (ir.action.report()): report record

        Returns:
            Char: composed name of the report
        """
        if docids:
            records = request.env[report.model].browse(docids)
            record_count = len(docids)
            if record_count == 1 and report.sudo().print_report_name:
                try:
                    print_report_name = report.sudo().print_report_name
                    extra_ctx = self._get_extra_context_for_single_record(
                        print_report_name,
                        ignore_expr=["object", "time"],
                    )

                    report_name = safe_eval(
                        print_report_name,
                        {
                            "object": records,
                            "time": safe_time,
                            **extra_ctx,
                        },
                    )
                except Exception:  # noqa: BLE001
                    # print_report_name is user data and can fail in any way.
                    report_name = f"{report.name}_report"
            else:
                report_name = f"{report.name} x{record_count}"
        else:
            report_name = report.name
        return report_name

    @route(type="http")
    def report_routes(self, reportname, docids=None, converter=None, **data):
        """Render a report. PDF responses are displayed inline.

        ``options`` and ``context`` are JSON strings already decoded by the
        HTTP layer. They are parsed with :func:`json.loads` only.

        Args:
            reportname (str): ``ir.actions.report`` technical name.
            docids (str | None): Comma-separated ids from the URL path.
            converter (str | None): ``pdf``, ``html``, or ``text``.
            **data: Query values, including ``options`` and ``context``.

        Returns:
            werkzeug.wrappers.Response: Inline PDF, or the core response
            for ``html`` and ``text``.

        Raises:
            AccessError: The user cannot read a record listed in ``docids``.
        """
        if converter != "pdf":
            return super().report_routes(
                reportname, docids=docids, converter=converter, **data
            )

        context = dict(request.env.context)
        if data.get("options"):
            data.update(json.loads(data.pop("options")))
        if data.get("context"):
            data["context"] = json.loads(data["context"])
            context.update(data["context"])
        # Company ids travel in the context. Without this, env.companies
        # falls back to every company the user can access.
        request.update_env(context=context)

        report = request.env["ir.actions.report"]._get_report_from_name(reportname)
        if not report:
            return request.not_found()

        parsed_docids = None
        if docids:
            try:
                parsed_docids = [int(docid) for docid in docids.split(",")]
                request.env[report.model].browse(parsed_docids).check_access("read")
            except (ValueError, AttributeError):
                return request.not_found()

        filename = f"{self._compose_report_file_name(parsed_docids, report)}.pdf"
        pdf = request.env["ir.actions.report"]._render_qweb_pdf(
            reportname, parsed_docids, data=data
        )[0]
        return request.make_response(
            pdf,
            headers=[
                ("Content-Type", "application/pdf"),
                ("Content-Length", len(pdf)),
                (
                    "Content-Disposition",
                    content_disposition(filename, disposition_type="inline"),
                ),
            ],
        )

    @route(type="http")
    def report_download(self, data, context=None, token=None, readonly=True):
        """Send a report file. PDFs use one inline ``Content-Disposition``.

        ``qweb-text`` (including ZPL) stays on the core download path.
        The file name comes from :meth:`_compose_report_file_name`, so a
        ``print_report_name`` that fails to evaluate still returns the
        rendered body.

        Args:
            data (str): JSON list ``[report_url, report_type]``.
            context (str | None): JSON context posted with the download.
            token (str | None): Legacy download token, forwarded for text.
            readonly (bool): Core route argument, forwarded for text.

        Returns:
            werkzeug.wrappers.Response: The report body.

        Raises:
            werkzeug.exceptions.InternalServerError: The PDF render or the
            access check failed. The response body is the serialized error.
        """
        requestcontent = json.loads(data)
        url, report_type = requestcontent[0], requestcontent[1]
        if not report_type.startswith("qweb-pdf"):
            return super().report_download(
                data, context=context, token=token, readonly=readonly
            )

        reportname = "???"
        try:
            reportname = url.split("/report/pdf/")[1].split("?")[0]
            docids = None
            if "/" in reportname:
                reportname, docids = reportname.split("/")
            if docids:
                return self.report_routes(
                    reportname, docids=docids, converter="pdf", context=context
                )
            query = url_parse(url).decode_query(cls=dict)
            if "context" in query:
                posted = json.loads(context or "{}")
                query_context = json.loads(query.pop("context"))
                context = json.dumps({**posted, **query_context})
            return self.report_routes(
                reportname, converter="pdf", context=context, **query
            )
        except Exception as error:
            _logger.warning(
                "Error while generating report %s", reportname, exc_info=True
            )
            error_body = {
                "code": 0,
                "message": "Odoo Server Error",
                "data": serialize_exception(error),
            }
            response = request.make_response(html_escape(json.dumps(error_body)))
            raise werkzeug.exceptions.InternalServerError(response=response) from error
