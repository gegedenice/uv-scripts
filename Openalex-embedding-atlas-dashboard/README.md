# OpenAlex Embedding Atlas Dashboard

A Python script that harvests research works from the OpenAlex API and visualizes them using an interactive embedding atlas dashboard. This tool allows you to explore and analyze academic publications through an interactive web interface with text embeddings and projections.

## Features

- **OpenAlex Integration**: Harvests research works from the OpenAlex API using custom queries. This harvest step is processed by the openalex-api-client library available here [https://github.com/gegedenice/openalex-api-client](https://github.com/gegedenice/openalex-api-client)
- **Data Processing and Derived Fields**: Automatically processes and transforms OpenAlex data into a format suitable for visualization
  - **Data Type Handling**: Automatically handles numeric, boolean, categorical, and datetime columns
  - **Derived Fields**: Extracts and processes pipe-separated values (countries, topics, fields, domains)

  >Warning: The pre-processing operations applied to the dataframe (type coercion, splitting of composite fields) are used here only to work around CLI limitations for demonstration purposes. In a real production context, using the Streamlit component or a React/Vite frontend is recommended, as they allow direct control over the configuration and rendering of Mosaic widgets.

- **Interactive Dashboard**: Launches an embedding-atlas dashboard (library available here [https://github.com/apple/embedding-atlas](https://github.com/apple/embedding-atlas)) with:
  - Text embeddings visualization
  - Interactive projections
  - Filtering and exploration capabilities

  >Embedding-Atlas is a lightweight exploration tool that automatically computes text embeddings (via the SentenceTransformers library, using the all-MiniLM-L6-v2 model by default), applies UMAP for dimensionality reduction, and performs automatic clustering and semantic labeling of the dataset. It generates an interactive Mosaic dashboard where users can inspect embeddings, explore clusters, filter records, analyze variable distributions, and navigate the dataset visually without writing any front-end code.

## Requirements

- Python 3.11 or higher
- `uv` package manager (for running the script)
- Internet connection (for OpenAlex API access)

## Installation

The script uses `uv` for dependency management. No separate installation is required - dependencies are automatically managed when you run the script.

Dependencies:
- `openalex-api-client` (from GitHub)
- `embedding-atlas`
- `pandas`

## Usage

### Basic Usage

```bash
uv run https://raw.githubusercontent.com/gegedenice/uv-scripts/main/Openalex-embedding-atlas-dashboard/app.py --query "YOUR_OPENALEX_QUERY"
```

### With Email (Recommended)

For better API rate limits and polite usage, provide your email:

```bash
uv run https://raw.githubusercontent.com/gegedenice/uv-scripts/main/Openalex-embedding-atlas-dashboard/app.py --query "YOUR_OPENALEX_FILTER_QUERY" --email "your.email@example.com"
```

### Example of filter queries

**Search by institution and publication date:**
```bash
uv run https://raw.githubusercontent.com/gegedenice/uv-scripts/main/Openalex-embedding-atlas-dashboard/app.py --query "authorships.institutions.lineage:i4210117840,publication_year:2024-" --email "your.email@example.com"
```

**Search by topic and OA true:**
```bash
uv run https://raw.githubusercontent.com/gegedenice/uv-scripts/main/Openalex-embedding-atlas-dashboard/app.py --query "topics.id:T11636,is_oa:true" --email "your.email@example.com"
```

**Search by author and most cited works:**
```bash
uv run https://raw.githubusercontent.com/gegedenice/uv-scripts/main/Openalex-embedding-atlas-dashboard/app.py --query "authorships.author.id:A5085171399,cited_by_count:>100" --email "your.email@example.com"
```

For more query examples, see the [OpenAlex API documentation](https://docs.openalex.org/how-to-use-the-api/get-lists-of-entities/filter-entity-lists).

## Command-Line Arguments

- `--query` (required): The OpenAlex query string to search for works. Uses OpenAlex filter syntax.
- `--email` (optional): Your email address for the API polite tool. Recommended for better rate limits.

## Open dashboard

Open localhost on the embedding-atlas default port 5055 : http://localhost:5055

## How It Works

1. **Data Harvesting**: The script connects to the OpenAlex API and retrieves works matching your query
2. **Data Processing**: 
   - Creates a combined text field from titles and abstracts
   - Converts numeric columns (citation counts, percentiles, etc.)
   - Processes boolean flags (top percentiles, open access status)
   - Handles categorical data (language, type, OA status)
   - Extracts derived fields from pipe-separated values
3. **Dashboard Launch**: Saves the processed data to a temporary parquet file and launches the embedding-atlas dashboard
4. **Visualization**: Opens an interactive web interface where you can explore the data

## Data Columns

The dashboard includes the following columns:

- **id**: OpenAlex work ID
- **title**
- **text**: Combined title and abstract
- **publication_year_cat**: Publication year as string
- **apc_paid**: Article processing charges
- **cited_by_count**: Number of citations
- **fwci**: Field-weighted citation impact
- **percentiles_value**: Citation percentile value
- **percentiles_is_in_top_1_percent**: Top 1% flag
- **percentiles_is_in_top_10_percent**: Top 10% flag
- **open_access_is_oa**: Open access status
- **open_access_oa_status**: OA status category
- **language**: Publication language
- **type**: Work type
- **primary_location_display_name**: Primary location
- **country_first**: First country code
- **field_main**: Main research field
- **domain_main**: Main research domain

## Stopping the Dashboard

Press `Ctrl+C` to stop the embedding-atlas server. The script will clean up temporary files automatically.

## Notes

- The script processes up to 50 works per page from OpenAlex
- Temporary parquet files are automatically cleaned up after the dashboard closes
- The embedding-atlas dashboard runs on an automatically assigned port (default: 5055)
- Make sure you have sufficient disk space for the temporary data file

## Troubleshooting

**Port already in use**: The `--auto-port` flag should automatically find an available port. If issues persist, ensure no other embedding-atlas instances are running.

**API rate limits**: If you encounter rate limiting, make sure to provide your email with the `--email` flag.

**Missing columns**: Some columns may not be present in all datasets. The script handles missing columns gracefully.

## License

See the main repository LICENSE file.
