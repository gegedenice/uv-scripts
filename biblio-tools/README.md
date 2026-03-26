# biblio-tools

[Version française](./README_fr.md)

`biblio-tools` is a small Python application that exposes bibliographic harvesting utilities through a `func-to-web` interface.

It currently supports three workflows:

- Harvest metadata from a text file containing Sudoc PPNs
- Harvest metadata from a Sudoc SRU query
- Fetch entities from OpenAlex and export the results

The app returns a preview table plus downloadable `CSV`, `XLSX`, and `JSON` files for each workflow.

## Features

- Simple browser UI powered by `func-to-web`
- Metadata extraction from Sudoc XML / UNIMARC records
- Configurable field mappings for Sudoc record extraction
- OpenAlex querying with `get`, `list`, `list_all`, and `count`
- Export helpers for `CSV`, `XLSX`, and `JSON`

## Project structure

```text
.
├── main.py
├── src/
│   └── harvest_tools.py
└── common/
    ├── exports.py
    ├── mappings.py
    ├── openalex.py
    ├── ppn.py
    └── sru.py
```

## Requirements

- Python 3.11+
- `uv`
- Network access to:
  - `https://www.sudoc.fr`
  - `https://sudoc.abes.fr`
  - OpenAlex API endpoints used by `openalex-api-client`

Dependencies are declared inline in [main.py](/home/root/PythonApps/biblio-tools/main.py).

## Run the application

From the project root:

```bash
UV_CACHE_DIR=/root/.cache/uv uv run main.py
```

The script header in [main.py](/home/root/PythonApps/biblio-tools/main.py) lets `uv` resolve the required dependencies automatically.

When started, the UI exposes two groups:

- `Sudoc`
  - `harvest_sudoc_metadata_from_ppn_list`
  - `harvest_sudoc_metadata_from_sru`
- `OpenAlex`
  - `harvest_entities_metadata_from_openalex`

## Workflows

### 1. Harvest metadata from a PPN file

Entry point: [src/harvest_tools.py](/home/root/PythonApps/biblio-tools/src/harvest_tools.py)

Use `harvest_sudoc_metadata_from_ppn_list` to upload a text file containing one PPN per line.

Processing flow:

1. The file is read and deduplicated
2. Each PPN is fetched from `https://www.sudoc.fr/<PPN>.xml`
3. Configured metadata fields are extracted from the returned XML
4. Results are assembled into a dataframe and exported

Default mappings:

```text
Titre|(200,a)|all:false
Premier Auteur|(200,f)|all:false
Autres auteurs|(200,g)|all:true
```

### 2. Harvest metadata from a Sudoc SRU query

Entry point: [src/harvest_tools.py](/home/root/PythonApps/biblio-tools/src/harvest_tools.py)

Use `harvest_sudoc_metadata_from_sru` to execute a Sudoc SRU query, paginate through all matching results, extract UNIMARC metadata, and export the dataset.

Important parameters:

- `query`: a strict Sudoc SRU query string
- `metadata_mappings`: extraction rules using the same syntax as the PPN workflow
- `batch_size`: number of records fetched per SRU request

Example query:

```text
tdo=y
```

The SRU implementation lives in [common/sru.py](/home/root/PythonApps/biblio-tools/common/sru.py).

### 3. Fetch data from OpenAlex

Entry point: [src/harvest_tools.py](/home/root/PythonApps/biblio-tools/src/harvest_tools.py)

Use `harvest_entities_metadata_from_openalex` to query OpenAlex through `openalex-api-client`.

Supported parameters:

- `method_type`: `count`, `get`, `list`, `list_all`
- `entity`: `work`, `author`, `institution`, `source`, `publisher`, `topic`, `funder`, `concept`
- `entity_id`: required for `get`
- `filter_value`: OpenAlex filter string
- `sort`: OpenAlex sort string
- `digest`: forwarded when supported
- `abstract`: forwarded for work endpoints when supported
- `per_page`: page size for list requests
- `api_key`: optional OpenAlex API key

Examples:

```text
method_type="get", entity="work", entity_id="W1234567890"
filter_value="publication_year:2024"
filter_value="authorships.author.id:A1234567890"
sort="publication_year:desc"
```

OpenAlex client setup and compatibility handling live in [common/openalex.py](/home/root/PythonApps/biblio-tools/common/openalex.py).

## Metadata mapping syntax

Sudoc extraction rules are parsed by [common/mappings.py](/home/root/PythonApps/biblio-tools/common/mappings.py).

Each mapping string uses this format:

```text
FieldName|(MARCField,Subfield)|all:true
FieldName|(MARCField,Subfield)|all:false
FieldName|(MARCField,Subfield)|all:true;sep: / 
FieldName|(MARCField,Subfield)|all:true;sep: ;list_sep: | 
```

In practice, the third segment must be written as:

```text
FieldName|(200,a)|all:false
FieldName|(700,a)|all:true
```

You can also provide multiple selectors:

```text
Titre complet|(200,a),(200,e)|all:true
Titre complet|(200,b),(200,c)|all:true;sep: 
Titre complet|(200,b),(200,c)|all:true;sep: / 
Members|(701,b,4=555),(701,a,4=555)|all:true;sep: 
```

Conditional filters are supported on the same field:

```text
Auteur principal|(700,a,4=070)|all:true
Auteur partiel|(700,a,4~=07)|all:true
```

Behavior:

- `all:false`: return the first matching value across selectors
- `all:true`: collect all matching values across selectors
- When multiple selectors share the same MARC field and filter, matching subfields are first combined within each field occurrence
- `sep:...` or `separator:...`: separator used inside one field occurrence when multiple selected subfields are combined
- `list_sep:...` or `list_separator:...`: separator used between repeated field occurrences
- if no `sep` is provided, subfields inside one occurrence are joined with a single space
- if no `list_sep` is provided, repeated occurrences are joined with ` | ` before export

Notes:

- Example:
  `Members|(701,b,4=555),(701,a,4=555)|all:true;sep: `
  returns `Michel Bouvier | Sébastien Jeannard`
- To change the outer separator too:
  `Members|(701,b,4=555),(701,a,4=555)|all:true;sep: ;list_sep:/`
  returns `Michel Bouvier/Sébastien Jeannard`
- Escape sequences are supported for both separators, for example:
  `sep:\n` for a newline or `sep:\t` for a tab

## Output files

All workflows return:

- A pandas dataframe for preview in the UI
- `<prefix>.csv`
- `<prefix>.xlsx`
- `<prefix>.json`

Export generation is implemented in [common/exports.py](/home/root/PythonApps/biblio-tools/common/exports.py).

Current filename prefixes:

- `ppn_metadata`
- `sru_metadata`
- `openalex_metadata`

## Internal design

### `main.py`

Registers the available tools with `func-to-web`.

### `src/harvest_tools.py`

Contains the user-facing workflow functions and dataframe normalization logic.

### `common/ppn.py`

Fetches Sudoc XML records by PPN and reads uploaded PPN files.

### `common/sru.py`

Calls the Sudoc SRU endpoint, counts matches, paginates results, and extracts embedded UNIMARC records.

### `common/mappings.py`

Parses mapping definitions and extracts values from UNIMARC XML.

### `common/openalex.py`

Creates the OpenAlex client and adapts to small API signature differences.

### `common/exports.py`

Builds downloadable `CSV`, `XLSX`, and `JSON` exports from pandas dataframes.

## Notes and limitations

- There is no `pyproject.toml`; dependency management currently relies on the inline `uv` script metadata in [main.py](/home/root/PythonApps/biblio-tools/main.py).
- Network failures are surfaced directly from `requests` / client exceptions.
- Sudoc query encoding is currently handled manually in [common/sru.py](/home/root/PythonApps/biblio-tools/common/sru.py), which may be fragile for more complex SRU queries.
- OpenAlex `count` currently delegates to the client count helper without forwarding the provided filter string; if filtered counts are required, that implementation should be reviewed in [common/openalex.py](/home/root/PythonApps/biblio-tools/common/openalex.py).

## Quick start examples

### Launch

```bash
UV_CACHE_DIR=/root/.cache/uv uv run main.py
```

### Example PPN file

```text
123456789
987654321
```

### Example mappings

```text
Titre|(200,a)|all:false
Sous-titre|(200,e)|all:false
Auteur principal|(700,a,4=070)|all:true
```
