{
    "name": "Common Base",
    "summary": "Common Base",
    "author": "OhMyDev",
    "category": "Hidden",
    "website": "https://www.ohmydev.org",
    "version": "20.0.1.0.0",
    "license": "LGPL-3",
    "contributors": [
        "tao-thewarat",
    ],
    "depends": [
        "base",
        "common_readme",
    ],
    "data": [
        "views/ir_module_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "common_base/static/src/scss/*.scss",
        ],
    },
    "application": False,
    "auto_install": ["base"],
    "installable": True,
}
