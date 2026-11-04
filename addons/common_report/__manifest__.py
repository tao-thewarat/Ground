{
    "name": "Common - Report",
    "summary": "Common Report",
    "author": "OhMyDev",
    "category": "Hidden",
    "website": "https://www.ohmydev.org",
    "version": "20.0.1.0.0",
    "license": "LGPL-3",
    "contributors": [
        "tao-thewarat",
    ],
    "depends": [
        "web",
        "common_readme",
    ],
    "data": [
        "templates/report_mixin_templates.xml",
    ],
    "assets": {
        "web.report_assets_common": [
            "common_report/static/src/css/*.css",
        ],
    },
    "installable": True,
}
