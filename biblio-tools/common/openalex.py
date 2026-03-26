import inspect


def _import_openalex_client():
    try:
        from openalex_api_client.client import OpenAlexClient
        return OpenAlexClient
    except Exception as exc:
        raise RuntimeError(
            "openalex-api-client is not available. Install it with: "
            "uv pip install git+https://github.com/gegedenice/openalex-api-client"
        ) from exc


def create_openalex_client(
    api_key: str | None = None,
    default_per_page: int = 25,
):
    OpenAlexClient = _import_openalex_client()
    kwargs = {"default_per_page": default_per_page}
    if api_key:
        kwargs["api_key"] = api_key

    try:
        return OpenAlexClient(**kwargs)
    except TypeError:
        # Backward compatibility if client version has no api_key argument.
        kwargs.pop("api_key", None)
        return OpenAlexClient(**kwargs)


def _filter_kwargs_for_callable(func, kwargs: dict) -> dict:
    sig = inspect.signature(func)
    accepts_var_kw = any(
        p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
    )
    if accepts_var_kw:
        return kwargs
    accepted = set(sig.parameters.keys())
    return {k: v for k, v in kwargs.items() if k in accepted}


def call_openalex(
    client,
    method_type: str,
    entity: str,
    entity_id: str | None = None,
    filter_value: str | None = None,
    sort: str | None = None,
    digest: bool = False,
    abstract: bool = False,
    per_page: int = 25,
):
    method_type = method_type.strip().lower()
    entity = entity.strip().lower()
    singular_entities = {
        "work": "work",
        "author": "author",
        "institution": "institution",
        "source": "source",
        "publisher": "publisher",
        "topic": "topic",
        "funder": "funder",
    }
    plural_entities = {
        "work": "works",
        "author": "authors",
        "institution": "institutions",
        "source": "sources",
        "publisher": "publishers",
        "topic": "topics",
        "funder": "funders",
    }
    if entity not in singular_entities:
        raise ValueError(f"Unsupported entity '{entity}'.")

    entity_one = singular_entities[entity]
    entity_many = plural_entities[entity]

    if method_type == "get":
        if not entity_id or not entity_id.strip():
            raise ValueError("`entity_id` is required for method_type='get' (use an OpenAlex ID).")
        method_name = f"get_{entity_one}"
        if not hasattr(client, method_name):
            raise ValueError(f"Client does not provide method '{method_name}'.")
        method = getattr(client, method_name)
        kwargs = {"digest": digest, "abstract": abstract}
        kwargs = _filter_kwargs_for_callable(method, kwargs)
        return method(entity_id.strip(), **kwargs)

    if method_type in {"list", "list_all"}:
        method_name = f"{method_type}_{entity_many}"
        if not hasattr(client, method_name):
            raise ValueError(f"Client does not provide method '{method_name}'.")
        method = getattr(client, method_name)

        kwargs = {"filter": filter_value, "sort": sort, "per_page": per_page}
        if entity_one == "work":
            kwargs["digest"] = digest
            kwargs["abstract"] = abstract

        kwargs = {k: v for k, v in kwargs.items() if v is not None and v != ""}
        kwargs = _filter_kwargs_for_callable(method, kwargs)
        return method(**kwargs)

    if method_type == "count":
        if not hasattr(client, "get_total_count"):
            raise ValueError("Client does not provide method 'get_total_count'.")
        method = getattr(client, "get_total_count")
        api_endpoint = f"/{entity_many}"
        try:
            return method(api_endpoint)
        except TypeError:
            # Compatibility with variants using keyword params.
            kwargs = {"api_endpoint": api_endpoint, "entity_type": entity_many}
            kwargs = _filter_kwargs_for_callable(method, kwargs)
            if kwargs:
                return method(**kwargs)
            raise

    raise ValueError("Unsupported method_type. Use get, list, list_all, or count.")
