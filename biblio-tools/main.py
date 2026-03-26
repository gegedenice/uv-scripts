#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "func-to-web",
#   "requests",
#   "pandas",
#   "openpyxl",
#   "markdown",
#   "openalex-api-client @ git+https://github.com/gegedenice/openalex-api-client",
# ]
# ///

import inspect
from pathlib import Path

from func_to_web import run
from markdown import markdown
from fastapi import Request
from starlette.templating import Jinja2Templates
import func_to_web.routes as ftw_routes
import func_to_web.server as ftw_server

from func_to_web.analyze_function import analyze
from func_to_web.build_form_fields import build_form_fields

from src.harvest_tools import (
    harvest_entities_metadata_from_openalex,
    harvest_sudoc_metadata_from_ppn_list,
    harvest_sudoc_metadata_from_sru,
)


def _patch_template_response_compat() -> None:
    """Adapt func-to-web's old TemplateResponse call style to newer Starlette."""
    if getattr(Jinja2Templates.TemplateResponse, "_biblio_tools_compat", False):
        return

    signature = inspect.signature(Jinja2Templates.TemplateResponse)
    params = list(signature.parameters)
    if params[1:3] != ["request", "name"]:
        return

    original = Jinja2Templates.TemplateResponse

    def compat_template_response(self, *args, **kwargs):
        if args and isinstance(args[0], str):
            name = args[0]
            context = args[1] if len(args) > 1 else kwargs.get("context")
            if not isinstance(context, dict) or "request" not in context:
                raise TypeError(
                    "TemplateResponse compatibility shim expected a context dict "
                    "containing 'request'."
                )

            request = context["request"]
            remaining = args[2:]
            return original(self, request, name, context, *remaining, **kwargs)

        return original(self, *args, **kwargs)

    compat_template_response._biblio_tools_compat = True
    Jinja2Templates.TemplateResponse = compat_template_response


def _render_docstring_markdown(description: str | None) -> str | None:
    if not description:
        return None

    return markdown(
        description,
        extensions=["extra", "sane_lists", "nl2br"],
    )


def _patch_func_to_web_markdown_docs() -> None:
    def register_function_routes(app, func, templates, has_auth):
        params = analyze(func)
        func_name = func.__name__.replace("_", " ").title()
        description = inspect.getdoc(func)
        description_html = _render_docstring_markdown(description)
        route = f"/{func.__name__}"
        submit_route = f"{route}/submit"

        async def form_view(request: Request):
            fields = build_form_fields(params)
            return templates.TemplateResponse(
                "form.html",
                {
                    "request": request,
                    "title": func_name,
                    "description": description,
                    "description_html": description_html,
                    "fields": fields,
                    "submit_url": submit_route,
                    "show_back_button": True,
                    "has_auth": has_auth,
                },
            )

        async def submit_view(request: Request):
            return await ftw_routes.handle_form_submission(request, func, params)

        app.get(route)(form_view)
        app.post(submit_route)(submit_view)

    def setup_single_function_routes(app, func, params, templates, has_auth):
        func_name = func.__name__.replace("_", " ").title()
        description = inspect.getdoc(func)
        description_html = _render_docstring_markdown(description)

        @app.get("/")
        async def form(request: Request):
            fields = build_form_fields(params)
            return templates.TemplateResponse(
                "form.html",
                {
                    "request": request,
                    "title": func_name,
                    "description": description,
                    "description_html": description_html,
                    "fields": fields,
                    "submit_url": "/submit",
                    "show_back_button": False,
                    "has_auth": has_auth,
                },
            )

        @app.post("/submit")
        async def submit(request: Request):
            return await ftw_routes.handle_form_submission(request, func, params)

    def setup_multiple_function_routes(app, funcs, templates, has_auth):
        @app.get("/")
        async def index(request: Request):
            tools = [
                {
                    "name": f.__name__.replace("_", " ").title(),
                    "path": f"/{f.__name__}",
                }
                for f in funcs
            ]
            return templates.TemplateResponse(
                "index.html",
                {"request": request, "tools": tools, "has_auth": has_auth},
            )

        for func in funcs:
            register_function_routes(app, func, templates, has_auth)

    def setup_grouped_function_routes(app, grouped_funcs, templates, has_auth):
        @app.get("/")
        async def index(request: Request):
            groups = []
            for group_name, funcs in grouped_funcs.items():
                tools = [
                    {
                        "name": f.__name__.replace("_", " ").title(),
                        "path": f"/{f.__name__}",
                    }
                    for f in funcs
                ]
                groups.append({"name": group_name, "tools": tools})

            return templates.TemplateResponse(
                "index.html",
                {"request": request, "groups": groups, "has_auth": has_auth},
            )

        for group_funcs in grouped_funcs.values():
            for func in group_funcs:
                register_function_routes(app, func, templates, has_auth)

    ftw_routes._register_function_routes = register_function_routes
    ftw_routes.setup_single_function_routes = setup_single_function_routes
    ftw_routes.setup_multiple_function_routes = setup_multiple_function_routes
    ftw_routes.setup_grouped_function_routes = setup_grouped_function_routes
    ftw_server.setup_single_function_routes = setup_single_function_routes
    ftw_server.setup_multiple_function_routes = setup_multiple_function_routes
    ftw_server.setup_grouped_function_routes = setup_grouped_function_routes


_patch_template_response_compat()
_patch_func_to_web_markdown_docs()


if __name__ == "__main__":
    run(
        {
            'Sudoc': [harvest_sudoc_metadata_from_ppn_list, harvest_sudoc_metadata_from_sru],
            'OpenAlex': [harvest_entities_metadata_from_openalex]
        },
        template_dir=Path(__file__).parent / "ui_templates",
    )
