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

from odoo.http.requestlib import Request
from odoo.tests import HttpCase, tagged

from odoo.addons.http_routing.tests.common import MockRequest
from odoo.addons.prt_report_attachment_preview.controllers.report import (
    CxReportController,
)


@tagged("post_install", "-at_install")
class TestCxReportController(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.controller = CxReportController()

    def test_get_extra_context_for_single_record(self):
        """
        Test the _get_extra_context_for_single_record method to ensure it correctly
        identifies and handles various expressions in the report name.
        """
        # Test case 1: Simple expression
        report_name = (
            "(object.state in ('draft', 'sent') and 'Quotation - %s' % (object.name)) "
            "or 'Order - %s' % (object.name)"
        )
        expected_result = {"object": "report"}
        result = self.controller._get_extra_context_for_single_record(report_name)
        self.assertEqual(
            result,
            expected_result,
            "Failed to correctly identify the variable in a simple expression.",
        )

        # Test case 2: Ignore expressions
        report_name = (
            "(object.state in ('draft', 'sent') and 'Quotation - %s' % (object.name)) "
            "or 'Order - %s' % (object.name)"
        )
        ignore_expr = ["object"]
        expected_result = {}
        result = self.controller._get_extra_context_for_single_record(
            report_name, ignore_expr=ignore_expr
        )
        self.assertEqual(
            result, expected_result, "Failed to correctly ignore specified expressions."
        )

        # Test case 3: No expressions
        report_name = "Simple Report Name"
        expected_result = {}
        result = self.controller._get_extra_context_for_single_record(report_name)
        self.assertEqual(
            result, expected_result, "Failed to handle report name with no expressions."
        )

    def test_compose_report_file_name(self):
        """
        Test the _compose_report_file_name method to ensure it correctly composes
        the report file name based on the provided document IDs and report action.
        """
        # Create a dummy report action for testing
        report_action = self.env["ir.actions.report"].create(
            {
                "name": "Test Report",
                "model": "res.partner",
                "report_type": "qweb-pdf",
                "report_name": "prt_report_attachment_preview.report_template",
                "print_report_name": '(object.name or "Unknown") + " Report"',
            }
        )
        test_partner_1 = self.env["res.partner"].create({"name": "Test Partner 1"})
        test_partner_2 = self.env["res.partner"].create({"name": "Test Partner 2"})

        # Test case 1: Valid print_report_name
        docids = [test_partner_1.id]
        with MockRequest(self.env):
            report_name = self.controller._compose_report_file_name(
                docids, report_action
            )
            self.assertIn(
                "Test Partner 1 Report",
                report_name,
                "Failed to compose the report file name correctly for a single record.",
            )

        # Test case 2: Valid print_report_name and several records
        docids.append(test_partner_2.id)
        with MockRequest(self.env):
            report_name = self.controller._compose_report_file_name(
                docids, report_action
            )
            self.assertIn(
                "Test Report x2",
                report_name,
                (
                    "Failed to compose the report"
                    " file name correctly for multiple records."
                ),
            )

        # Test case 3: Without docids
        with MockRequest(self.env):
            report_name = self.controller._compose_report_file_name([], report_action)
            self.assertIn(
                "Test Report",
                report_name,
                (
                    "Failed to compose the report file name"
                    " correctly when no docids are provided."
                ),
            )

        # Test case 4: Invalid print_report_name (non-string)
        # Set print_report_name to a non-string value
        report_action.print_report_name = False
        with MockRequest(self.env):
            report_name = self.controller._compose_report_file_name(
                docids, report_action
            )
            self.assertEqual(
                report_name,
                f"{report_action.name} x2",
                "Failed to handle non-string print_report_name correctly.",
            )

    def _create_preview_report(self, suffix, echo_marker=False):
        """Create a qweb-pdf report whose body is HTML under test mode.

        Args:
            suffix (str): Unique piece of the technical report name.
            echo_marker (bool): When true, the template prints ``marker``
                from the report options.

        Returns:
            ir.actions.report: The report action.
        """
        report_name = f"prt_report_attachment_preview.preview_{suffix}"
        report = self.env["ir.actions.report"].create(
            {
                "name": "Test Report",
                "model": "res.partner",
                "report_type": "qweb-pdf",
                "report_name": report_name,
                "print_report_name": "'OK'",
            }
        )
        if echo_marker:
            arch = '<main><div t-out="marker"/></main>'
        else:
            arch = "<main><div>PREVIEW-BODY</div></main>"
        self.env["ir.ui.view"].create(
            {
                "type": "qweb",
                "name": report_name,
                "key": report_name,
                "arch": arch,
            }
        )
        return report

    def _controller_response(self, method, *args, **kwargs):
        """Call a controller method under MockRequest.

        MockRequest does not implement ``make_response`` or ``update_env``.
        Bind the real request methods so the call returns a response and
        applies the posted context.

        Args:
            method (callable): Controller method to call.
            *args: Positional arguments forwarded to ``method``.
            **kwargs: Keyword arguments forwarded to ``method``.

        Returns:
            werkzeug.wrappers.Response: The controller response.
        """
        with MockRequest(self.env) as http_request:
            http_request.make_response = Request.make_response.__get__(http_request)
            http_request.update_env = Request.update_env.__get__(http_request)
            http_request.not_found = Request.not_found.__get__(http_request)
            return method(*args, **kwargs)

    def _content_disposition(self, response):
        """Return every Content-Disposition value on ``response``.

        Args:
            response (werkzeug.wrappers.Response): Controller response.

        Returns:
            list[str]: Header values.
        """
        return response.headers.getlist("Content-Disposition")

    def test_report_routes_keeps_plus_in_options(self):
        """A second URL decode would turn a ``+`` in options JSON into a space."""
        report = self._create_preview_report("plus", echo_marker=True)
        options = json.dumps({"marker": "Label+Name"})
        response = self._controller_response(
            self.controller.report_routes,
            report.report_name,
            converter="pdf",
            options=options,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Label+Name", response.get_data(as_text=True))

    def test_report_routes_label_payload_skips_docid_access(self):
        """Label options are not document ids, so they are not access-checked."""
        report = self._create_preview_report("labels")
        partner = self.env["res.partner"].create({"name": "Label Target"})
        checked_ids = []
        origin = self.env.registry["res.partner"].check_access

        def _check_access(records, operation):
            checked_ids.append(list(records.ids))
            return origin(records, operation)

        self.patch(self.env.registry["res.partner"], "check_access", _check_access)
        options = json.dumps(
            {
                "labels": [{"name": "Label+Name"}],
                "label_template": "product.report_simple_label2x7",
                "layout": {"rows": 7, "columns": 2},
            }
        )
        context = json.dumps(
            {"active_ids": [partner.id], "active_model": "res.partner"}
        )
        response = self._controller_response(
            self.controller.report_routes,
            report.report_name,
            converter="pdf",
            options=options,
            context=context,
        )
        dispositions = self._content_disposition(response)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(dispositions), 1)
        self.assertIn("inline", dispositions[0])
        self.assertNotIn("attachment", dispositions[0])
        self.assertNotIn(partner.id, [docid for ids in checked_ids for docid in ids])

    def test_report_download_survives_print_report_name_error(self):
        """A print_report_name that fails to eval must still return the body."""
        report = self._create_preview_report("bad_name")
        report.print_report_name = "object.this_field_does_not_exist"
        partner = self.env["res.partner"].create({"name": "One Partner"})
        url = f"/report/pdf/{report.report_name}/{partner.id}"
        response = self._controller_response(
            self.controller.report_download,
            json.dumps([url, "qweb-pdf"]),
            context="{}",
        )
        body = response.get_data(as_text=True)
        dispositions = self._content_disposition(response)
        self.assertEqual(response.status_code, 200)
        self.assertIn("PREVIEW-BODY", body)
        self.assertNotIn("Odoo Server Error", body)
        self.assertEqual(len(dispositions), 1)
        self.assertIn("inline", dispositions[0])
        self.assertIn("Report_report", dispositions[0])
