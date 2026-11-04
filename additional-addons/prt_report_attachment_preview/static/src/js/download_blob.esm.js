/** @odoo-module **/

import {ConnectionLostError, makeErrorFromResponse} from "@web/core/network/rpc";
import {_t} from "@web/core/l10n/translation";
import {parse} from "@web/core/network/download";

const POPUP_WARNING = _t(
    "A popup window with your report was blocked. You " +
        "may need to change your browser settings to allow " +
        "popup windows for this page."
);

/**
 * Read a failed download body the way ``configureBlobDownloadXHR`` does.
 *
 * @param {Blob} blob
 * @param {Number} status
 * @returns {Promise<Error>}
 */
function readDownloadError(blob, status) {
    return new Promise((resolve) => {
        const decoder = new FileReader();
        decoder.onload = () => {
            const contents = decoder.result;
            const doc = new DOMParser().parseFromString(contents, "text/html");
            const nodes =
                doc.body.children.length === 0 ? [doc.body] : [...doc.body.children];
            let error = null;
            try {
                const node = nodes[1] || nodes[0];
                error = JSON.parse(node.textContent);
            } catch {
                const first = nodes.length > 0 ? nodes[0].textContent : "";
                const second = nodes.length > 1 ? nodes[1].textContent : "";
                error = {
                    message: "Arbitrary Uncaught Python Exception",
                    data: {
                        debug: `${status}\n${first}${second}`,
                    },
                };
            }
            resolve(makeErrorFromResponse(error));
        };
        decoder.readAsText(blob);
    });
}

/**
 * POST form fields and resolve with the file when the response is a
 * successful download. Does not save the file.
 *
 * @param {String} url
 * @param {Object} fields
 * @param {Boolean} includeCsrf
 * @returns {Promise<{blob: Blob, filename: String|null, mimetype: String}>}
 */
export function postFormBlob(url, fields, includeCsrf) {
    return new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.open("POST", url);
        const form = new FormData();
        for (const [key, value] of Object.entries(fields)) {
            form.append(key, value);
        }
        form.append("token", "dummy-because-api-expects-one");
        if (includeCsrf && odoo.csrf_token) {
            form.append("csrf_token", odoo.csrf_token);
        }
        xhr.responseType = "blob";
        xhr.onload = async () => {
            const mimetype = xhr.response.type;
            const header = (xhr.getResponseHeader("Content-Disposition") || "").replace(
                /;$/,
                ""
            );
            const filename = header ? parse(header).parameters.filename : null;
            if (xhr.status === 200 && (mimetype !== "text/html" || filename)) {
                resolve({blob: xhr.response, filename, mimetype});
                return;
            }
            if (xhr.status === 502) {
                reject(new ConnectionLostError(url));
                return;
            }
            reject(await readDownloadError(xhr.response, xhr.status));
        };
        xhr.onerror = () => {
            reject(new ConnectionLostError(url));
        };
        xhr.send(form);
    });
}

/**
 * Open a blob in a new tab.
 *
 * @param {Blob} blob
 * @returns {Window|null}
 */
export function openBlobPreview(blob) {
    return window.open(URL.createObjectURL(blob), "_blank");
}

/**
 * Show the popup-blocked warning when ``previewWindow`` is missing.
 *
 * @param {Object} notification
 * @param {Window|null} previewWindow
 */
export function warnIfPopupBlocked(notification, previewWindow) {
    if (previewWindow) {
        return;
    }
    notification.add(POPUP_WARNING, {type: "warning"});
}
