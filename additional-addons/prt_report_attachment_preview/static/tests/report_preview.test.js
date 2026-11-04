/** @odoo-module **/

import "@prt_report_attachment_preview/js/account_report_download.esm";
import {afterEach, describe, expect, queryOne, test} from "@odoo/hoot";
import {animationFrame, runAllTimers} from "@odoo/hoot-mock";
import {
    getService,
    mountWithCleanup,
    onRpc,
    patchWithCleanup,
} from "@web/../tests/web_test_helpers";
import {WebClient} from "@web/webclient/webclient";
import {download} from "@web/core/network/download";
import {loadEngineState} from "@prt_report_attachment_preview/js/report.esm";
import {registry} from "@web/core/registry";

describe.current.tags("headless");

const PRINTER_KEY = "test_printer";
const ACCOUNT_KEY = "ir_actions_account_report_download";

afterEach(() => {
    delete loadEngineState.reportingEngineStatusProm;
    const handlers = registry.category("ir.actions.report handlers");
    if (handlers.contains(PRINTER_KEY)) {
        handlers.remove(PRINTER_KEY);
    }
});

function installPreview(options = {}) {
    const preview = {
        closed: false,
        location: {href: "about:blank"},
        document: {
            contentType: "text/html",
            body: {textContent: ""},
        },
        listeners: {},
        addEventListener(type, fn) {
            this.listeners[type] = fn;
        },
        close() {
            this.closed = true;
        },
    };
    const opened = [];
    const submitted = [];
    patchWithCleanup(window, {
        open(url, name) {
            opened.push({url: String(url), name});
            if (options.block) {
                return null;
            }
            return preview;
        },
    });
    patchWithCleanup(HTMLFormElement.prototype, {
        submit() {
            const fields = {};
            for (const element of this.elements) {
                if (element.name) {
                    fields[element.name] = element.value;
                }
            }
            submitted.push({action: this.action, target: this.target, fields});
            if (options.errorText) {
                preview.document.contentType = "text/html";
                preview.document.body.textContent = options.errorText;
            } else {
                preview.document.contentType = "application/pdf";
                preview.document.body.textContent = "";
            }
            preview.location.href = this.action;
            const onLoad = preview.listeners.load;
            if (onLoad) {
                onLoad();
            }
        },
    });
    return {preview, opened, submitted};
}

function labelAction() {
    return {
        type: "ir.actions.report",
        report_type: "qweb-pdf",
        report_name: "product.report_producttemplatelabel2x7",
        data: {
            labels: [{name: "A+B"}],
            label_template: "product.report_simple_label2x7",
            layout: {rows: 7, columns: 2},
        },
        context: {active_ids: [1, 2], active_model: "product.template"},
    };
}

test("a selected printer runs before the preview", async () => {
    registry.category("ir.actions.report handlers").add(
        PRINTER_KEY,
        (action) => {
            expect.step("printer");
            return Boolean(
                action.context && action.context.jobs && action.context.jobs.length
            );
        },
        {sequence: 50}
    );
    const {submitted} = installPreview();
    onRpc("/report/get_pdf_engine_state", () => "ok");
    await mountWithCleanup(WebClient);
    await getService("action").doAction({
        ...labelAction(),
        context: {jobs: [{type: "epos"}], active_ids: [1]},
    });
    expect.verifySteps(["printer"]);
    expect(submitted).toHaveLength(0);
});

test("preview posts the label payload with no document ids", async () => {
    const previousCsrf = odoo.csrf_token;
    odoo.csrf_token = "csrf-test";
    const {submitted, opened} = installPreview();
    let openedBeforeEngineCheck = 0;
    onRpc("/report/get_pdf_engine_state", () => {
        openedBeforeEngineCheck = opened.length;
        return "ok";
    });
    await mountWithCleanup(WebClient);
    try {
        await getService("action").doAction(labelAction());
    } finally {
        odoo.csrf_token = previousCsrf;
    }
    expect(openedBeforeEngineCheck).toBe(1);
    expect(submitted).toHaveLength(1);
    expect(opened[0].url).toBe("");
    expect(submitted[0].action).toBe("/report/download");
    expect(submitted[0].target).toBe(opened[0].name);
    const data = JSON.parse(submitted[0].fields.data);
    const [url, reportType] = data;
    expect(reportType).toBe("qweb-pdf");
    expect(url.startsWith("/report/pdf/product.report_producttemplatelabel2x7?")).toBe(
        true
    );
    expect(url.includes("/1,2")).toBe(false);
    expect(decodeURIComponent(url)).toInclude("A+B");
    const context = JSON.parse(submitted[0].fields.context);
    expect(context.active_ids).toEqual([1, 2]);
    expect(submitted[0].fields.token).toBe("dummy-because-api-expects-one");
    expect(submitted[0].fields.csrf_token).toBe("csrf-test");
});

test("a named PDF engine is sent to the state route", async () => {
    installPreview();
    onRpc("/report/get_pdf_engine_state", async (request) => {
        const {params} = await request.json();
        expect(params.engine_name).toBe("wkhtmltopdf");
        return "ok";
    });
    await mountWithCleanup(WebClient);
    await getService("action").doAction({
        type: "ir.actions.report",
        report_type: "qweb-pdf-wkhtmltopdf",
        report_name: "sale.report_saleorder",
        context: {active_ids: [7]},
    });
});

test("a broken engine opens the HTML report and notifies", async () => {
    const {opened, preview, submitted} = installPreview();
    onRpc("/report/get_pdf_engine_state", () => "broken");
    await mountWithCleanup(WebClient);
    await getService("action").doAction({
        type: "ir.actions.report",
        report_type: "qweb-pdf",
        report_name: "sale.report_saleorder",
        context: {active_ids: [7]},
    });
    await animationFrame();
    expect(submitted).toHaveLength(0);
    expect(opened[0].url).toBe("");
    expect(preview.location.href).toMatch(/^\/report\/html\/sale\.report_saleorder\/7/);
    expect(queryOne(".o_notification_content").textContent).toMatch(/broken/);
});

test("each PDF engine is checked on its own", async () => {
    installPreview();
    const seen = [];
    onRpc("/report/get_pdf_engine_state", async (request) => {
        const {params} = await request.json();
        seen.push(params.engine_name || "");
        return params.engine_name === "paper-muncher" ? "broken" : "ok";
    });
    await mountWithCleanup(WebClient);
    const action = getService("action");
    await action.doAction({
        type: "ir.actions.report",
        report_type: "qweb-pdf-wkhtmltopdf",
        report_name: "sale.report_saleorder",
        context: {active_ids: [7]},
    });
    await action.doAction({
        type: "ir.actions.report",
        report_type: "qweb-pdf-paper-muncher",
        report_name: "sale.report_saleorder",
        context: {active_ids: [7]},
    });
    expect(seen).toEqual(["wkhtmltopdf", "paper-muncher"]);
});

test("an upgrade warning still posts the PDF", async () => {
    const {submitted} = installPreview();
    onRpc("/report/get_pdf_engine_state", () => "upgrade");
    await mountWithCleanup(WebClient);
    await getService("action").doAction(labelAction());
    await animationFrame();
    expect(submitted).toHaveLength(1);
    expect(queryOne(".o_notification_content").textContent).toMatch(/upgrade/);
});

test("a blocked popup does not post the report", async () => {
    const {submitted} = installPreview({block: true});
    onRpc("/report/get_pdf_engine_state", () => "ok");
    await mountWithCleanup(WebClient);
    await getService("action").doAction(labelAction());
    await animationFrame();
    expect(submitted).toHaveLength(0);
    expect(queryOne(".o_notification_content").textContent).toMatch(/popup window/);
});

test("a failed PDF is shown in the client and the tab is closed", async () => {
    const errorText = JSON.stringify({
        code: 0,
        message: "Odoo Server Error",
        data: {name: "odoo.exceptions.AccessError", message: "nope"},
    });
    const {preview} = installPreview({errorText});
    onRpc("/report/get_pdf_engine_state", () => "ok");
    await mountWithCleanup(WebClient);
    await expect(getService("action").doAction(labelAction())).rejects.toThrow(
        "Odoo Server Error"
    );
    expect(preview.closed).toBe(true);
});

test("qweb-text still downloads", async () => {
    const {submitted, opened} = installPreview();
    patchWithCleanup(download, {
        _download() {
            expect.step("download");
            return Promise.resolve();
        },
    });
    await mountWithCleanup(WebClient);
    await getService("action").doAction({
        type: "ir.actions.report",
        report_type: "qweb-text",
        report_name: "stock.label_product_product_view",
    });
    expect.verifySteps(["download"]);
    expect(submitted).toHaveLength(0);
    expect(opened).toHaveLength(0);
});

test("the accounting handler replaces the registry entry without looping", () => {
    const handlers = registry.category("action_handlers");
    if (handlers.contains(ACCOUNT_KEY)) {
        handlers.remove(ACCOUNT_KEY);
    }
    const foreign = () => "foreign";
    handlers.add(ACCOUNT_KEY, foreign);
    const ours = handlers.get(ACCOUNT_KEY);
    expect(ours).not.toBe(foreign);
    const again = () => "again";
    handlers.add(ACCOUNT_KEY, again, {force: true});
    expect(handlers.get(ACCOUNT_KEY)).toBe(ours);
});

function installXhr(response, onSend) {
    function FakeXHR() {
        this.status = response.status;
        this.response = response.body;
        this.responseHeader = response.header || "";
    }
    FakeXHR.prototype.open = function (method, url) {
        this.method = method;
        this.url = url;
    };
    FakeXHR.prototype.send = function (body) {
        if (onSend) {
            onSend();
        }
        this.body = body;
        this.onload();
    };
    FakeXHR.prototype.getResponseHeader = function () {
        return this.responseHeader;
    };
    patchWithCleanup(window, {XMLHttpRequest: FakeXHR});
}

test("an accounting PDF opens in a tab and other formats download", async () => {
    const opened = [];
    const saved = [];
    const events = [];
    patchWithCleanup(window, {
        open(url) {
            events.push("open");
            const preview = {
                closed: false,
                location: {href: String(url)},
                close() {
                    this.closed = true;
                },
            };
            opened.push(preview);
            return preview;
        },
    });
    patchWithCleanup(HTMLAnchorElement.prototype, {
        click() {
            saved.push(this.getAttribute("download"));
        },
    });
    installXhr(
        {
            status: 200,
            body: new Blob(["%PDF"], {type: "application/pdf"}),
        },
        () => events.push("send")
    );
    await mountWithCleanup(WebClient);
    await getService("action").doAction({
        type: ACCOUNT_KEY,
        data: {
            options: JSON.stringify({report_id: 9}),
            file_generator: "export_to_pdf",
            no_closing_after_download: true,
            next_action: {type: "ir.actions.client", tag: "missing_preview_tag"},
        },
    });
    expect(events.slice(0, 2)).toEqual(["open", "send"]);
    expect(opened).toHaveLength(1);
    expect(opened[0].location.href.startsWith("blob:")).toBe(true);
    expect(saved).toHaveLength(0);

    installXhr(
        {
            status: 200,
            header: 'attachment; filename="balance.xlsx"',
            body: new Blob(["xlsx"], {
                type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            }),
        },
        () => events.push("send")
    );
    await getService("action").doAction({
        type: ACCOUNT_KEY,
        data: {
            options: JSON.stringify({report_id: 9}),
            output_format: "xlsx",
        },
    });
    await runAllTimers();
    expect(opened).toHaveLength(1);
    expect(events.filter((event) => event === "open")).toHaveLength(1);
    expect(saved).toEqual(["balance.xlsx"]);
});

test("an accounting file error opens the error wizard", async () => {
    installXhr({
        status: 500,
        body: new Blob(
            [
                JSON.stringify({
                    code: 200,
                    message: "Odoo Server Error",
                    data: {
                        name: "AccountReportFileDownloadException",
                        arguments: ["The file", "is invalid"],
                    },
                }),
            ],
            {type: "text/html"}
        ),
    });
    onRpc("open_account_report_file_download_error_wizard", ({args}) => {
        expect.step(`${args[0]}:${args[1]}:${args[2]}`);
        return {type: "ir.actions.act_window_close"};
    });
    await mountWithCleanup(WebClient);
    await getService("action").doAction({
        type: ACCOUNT_KEY,
        data: {options: JSON.stringify({report_id: 9})},
    });
    expect.verifySteps(["9:The file:is invalid"]);
});
