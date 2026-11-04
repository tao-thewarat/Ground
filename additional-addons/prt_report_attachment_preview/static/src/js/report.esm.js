/** @odoo-module **/

import {makeErrorFromResponse, rpc} from "@web/core/network/rpc";
import {NotificationPlugin} from "@web/core/notifications/notification_plugin";
import {_t} from "@web/core/l10n/translation";
import {getReportUrl} from "@web/webclient/actions/reports/utils";
import {registry} from "@web/core/registry";
import {usePlugin} from "@odoo/owl";
import {user} from "@web/core/user";
import {warnIfPopupBlocked} from "./download_blob.esm";

/**
 * Message for a PDF engine state, copied from core ``getPdfEngineMessage``.
 * ``ok`` has no message.
 *
 * @param {String} status
 * @returns {String|undefined}
 */
function pdfEngineMessage(status) {
    const messages = {
        broken: _t(
            "Your installation of PDF engine seems to be broken, check with the administrator. The report will be shown in html."
        ),
        install: _t(
            "Unable to find the PDF engine on this system. The report will be shown in html."
        ),
        upgrade: _t(
            "You should upgrade your version of the PDF engine in order to get a correct render it."
        ),
        workers: _t(
            "You need to start Odoo with at least two workers to print a pdf version of the reports."
        ),
    };
    return messages[status];
}

/**
 * Engine suffix of ``qweb-pdf-<engine>``. A bare ``qweb-pdf`` has none.
 *
 * @param {String} reportType
 * @returns {String}
 */
function engineNameFromReportType(reportType) {
    const prefix = "qweb-pdf-";
    if (reportType.startsWith(prefix)) {
        return reportType.slice(prefix.length);
    }
    return "";
}

/**
 * Engine state for one PDF engine.
 *
 * wkhtmltopdf and paper-muncher each report their own state, so the
 * promise is cached per engine name. A bare ``qweb-pdf`` uses an empty
 * name, and the server then picks the default engine.
 *
 * @param {String} engineName
 * @returns {Promise<String>}
 */
export function loadEngineState(engineName) {
    const params = {};
    if (engineName) {
        params.engine_name = engineName;
    }
    const cache = (loadEngineState.reportingEngineStatusProm ||= {});
    cache[engineName] ||= rpc("/report/get_pdf_engine_state", params);
    return cache[engineName];
}

/**
 * Read a failed preview tab.
 *
 * The controller answers with ``text/html`` whose text is the JSON
 * ``makeErrorFromResponse`` expects. A PDF viewer is not that document.
 *
 * @param {Window} preview
 * @returns {Error|null}
 */
function readPreviewError(preview) {
    let doc = null;
    try {
        doc = preview.document;
    } catch {
        return null;
    }
    if (!doc || doc.contentType === "application/pdf") {
        return null;
    }
    const text = (doc.body && doc.body.textContent ? doc.body.textContent : "").trim();
    if (!text.startsWith("{")) {
        return null;
    }
    try {
        const payload = JSON.parse(text);
        if (!payload || payload.message !== "Odoo Server Error" || !payload.data) {
            return null;
        }
        return makeErrorFromResponse(payload);
    } catch {
        return null;
    }
}

/**
 * Open the PDF in a new tab by posting ``/report/download``.
 *
 * The tab must load that response. A blob URL has no
 * ``Content-Disposition``, so the browser saves the file as
 * ``document.pdf`` instead of the report name.
 *
 * When the tab's document is the serialized server error, the promise
 * rejects with that error and the tab is closed. The action service then
 * shows it in the web client, and the handler does not return true.
 *
 * ``preview`` is opened by the handler before any await, so the browser
 * still counts it as part of the user click.
 *
 * @param {Object} action
 * @param {Window} preview
 * @param {String} windowName target name the form posts into
 * @returns {Promise<void>}
 */
function openPdfReport(action, preview, windowName) {
    if (preview.closed) {
        return Promise.resolve();
    }
    const form = document.createElement("form");
    form.method = "POST";
    form.action = "/report/download";
    form.target = windowName;
    form.style.display = "none";
    const fields = {
        data: JSON.stringify([getReportUrl(action, "pdf"), action.report_type]),
        context: JSON.stringify({...user.context, ...action.context}),
        token: "dummy-because-api-expects-one",
    };
    if (odoo.csrf_token) {
        fields.csrf_token = odoo.csrf_token;
    }
    for (const [key, value] of Object.entries(fields)) {
        const input = document.createElement("input");
        input.type = "hidden";
        input.name = key;
        input.value = value;
        form.appendChild(input);
    }
    document.body.appendChild(form);
    return new Promise((resolve, reject) => {
        const settle = () => {
            if (preview.closed) {
                resolve();
                return;
            }
            const error = readPreviewError(preview);
            if (error) {
                preview.close();
                reject(error);
                return;
            }
            let href = "";
            try {
                href = preview.location.href;
            } catch {
                resolve();
                return;
            }
            if (href && href !== "about:blank") {
                resolve();
            }
        };
        preview.addEventListener("load", settle);
        form.submit();
        // Removing the form in this turn cancels the POST in some browsers.
        setTimeout(() => form.remove());
    });
}

registry.category("ir.actions.report handlers").add(
    "open_report_handler",
    async function (action) {
        const notification = usePlugin(NotificationPlugin);
        if (!action.report_type || !action.report_type.startsWith("qweb-pdf")) {
            return false;
        }
        // Open before the engine RPC. After an await the browser no longer
        // treats window.open as part of the click and blocks the tab.
        const windowName = `odoo_pdf_${Date.now()}`;
        const preview = window.open("", windowName);
        if (!preview || preview.closed) {
            warnIfPopupBlocked(notification, null);
            return true;
        }
        let state = "";
        try {
            state = await loadEngineState(engineNameFromReportType(action.report_type));
        } catch (error) {
            if (!preview.closed) {
                preview.close();
            }
            throw error;
        }
        const message = pdfEngineMessage(state);
        if (message) {
            notification.add(message, {
                sticky: true,
                title: _t("Report"),
            });
        }
        if (preview.closed) {
            return true;
        }
        if (state === "ok" || state === "upgrade") {
            await openPdfReport(action, preview, windowName);
            return true;
        }
        preview.location.href = getReportUrl(action, "html", user.context);
        return true;
    },
    // The printer handler uses the default sequence (50) and returns false
    // when nothing is selected. Running later lets that handler print first.
    {sequence: 100}
);
