#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "func-to-web",
#   "requests",
#   "pandas",
#   "openpyxl",
#   "openalex-api-client @ git+https://github.com/gegedenice/openalex-api-client",
# ]
# ///

import inspect

from func_to_web import run
from starlette.templating import Jinja2Templates

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


_patch_template_response_compat()


if __name__ == "__main__":
    run({
        'Sudoc': [harvest_sudoc_metadata_from_ppn_list, harvest_sudoc_metadata_from_sru],
        'OpenAlex': [harvest_entities_metadata_from_openalex]
    })
