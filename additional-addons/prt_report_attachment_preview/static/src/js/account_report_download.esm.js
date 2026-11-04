/** @odoo-module **/

import {openBlobPreview, postFormBlob, warnIfPopupBlocked} from "./download_blob.esm";
import {ActionPlugin} from "@web/webclient/actions/action_plugin";
import {NotificationPlugin} from "@web/core/notifications/notification_plugin";
import {ORM} from "@web/core/orm_plugin";
import {UIPlugin} from "@web/core/ui/ui_plugin";
import {downloadFile} from "@web/core/network/download";
import {registry} from "@web/core/registry";
import {usePlugin} from "@odoo/owl";

const HANDLER_KEY = "ir_actions_account_report_download";

/**
 * Show a downloaded accounting file.
 *
 * A PDF uses the tab opened before the request. Any other type is saved,
 * and that tab is closed.
 *
 * @param {Object} result
 * @param {Blob} result.blob
 * @param {String|null} result.filename
 * @param {String} result.mimetype
 * @param {Window|null} preview
 * @param {Boolean} wantsPdf
 * @param {Object} notification
 */
function showDownloadedFile(result, preview, wantsPdf, notification) {
    if (result.mimetype === "application/pdf") {
        if (preview && !preview.closed) {
            preview.location.href = URL.createObjectURL(result.blob);
            return;
        }
        if (!wantsPdf) {
            warnIfPopupBlocked(notification, openBlobPreview(result.blob));
        }
        return;
    }
    if (preview && !preview.closed) {
        preview.close();
    }
    downloadFile(result.blob, result.filename, result.mimetype);
}

/**
 * Preview an accounting PDF. Other export types stay file downloads.
 * Registered in place of the enterprise handler when that handler exists.
 *
 * @param {Object} params
 * @param {Object} params.action
 */
async function executeAccountReportDownload({action}) {
    const notification = usePlugin(NotificationPlugin);
    const ui = usePlugin(UIPlugin);
    const actionPlugin = usePlugin(ActionPlugin);
    const orm = usePlugin(ORM);
    const data = action.data;
    // A PDF tab has to be opened before the download request. The response
    // type is only known afterwards, and a later window.open is blocked.
    const wantsPdf = data.file_generator === "export_to_pdf";
    let preview = null;
    if (wantsPdf) {
        preview = window.open("", "_blank");
        if (!preview || preview.closed) {
            warnIfPopupBlocked(notification, null);
            preview = null;
        }
    }
    ui.block();
    try {
        const result = await postFormBlob("/account_reports", data, false);
        showDownloadedFile(result, preview, wantsPdf, notification);
        if (data.no_closing_after_download) {
            return;
        }
        if (data.next_action) {
            actionPlugin.doAction(data.next_action);
            return;
        }
        actionPlugin.doAction({type: "ir.actions.act_window_close"});
    } catch (error) {
        if (preview && !preview.closed) {
            preview.close();
        }
        if (error.exceptionName !== "AccountReportFileDownloadException") {
            throw error;
        }
        const reportOptions = JSON.parse(data.options);
        const reportAction = await orm.call(
            "account.report",
            "open_account_report_file_download_error_wizard",
            [reportOptions.report_id, error.data.arguments[0], error.data.arguments[1]]
        );
        actionPlugin.doAction(reportAction);
    } finally {
        ui.unblock();
    }
}

/**
 * Replace the enterprise download handler. A second replace of our own
 * function would loop, because ``add`` fires ``UPDATE``.
 */
function installAccountReportDownload() {
    const handlers = registry.category("action_handlers");
    if (!handlers.contains(HANDLER_KEY)) {
        return;
    }
    if (handlers.get(HANDLER_KEY) === executeAccountReportDownload) {
        return;
    }
    handlers.add(HANDLER_KEY, executeAccountReportDownload, {force: true});
}

installAccountReportDownload();
registry
    .category("action_handlers")
    .addEventListener("UPDATE", installAccountReportDownload);
