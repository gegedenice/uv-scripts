#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "openalex-api-client @ git+https://github.com/gegedenice/openalex-api-client",
#   "embedding-atlas",
#   "pandas",
# ]
# ///
"""OpenAlex embedding atlas dashboard application."""
import argparse
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

import pandas as pd
from openalex_api_client import OpenAlexClient

# Constants
NUMERIC_COLUMNS = [
    "apc_paid",
    "referenced_works_count",
    "cited_by_count",
    "countries_distinct_count",
    "institutions_distinct_count",
    "locations_count",
    "fwci",
    "percentiles_value",
]

BOOLEAN_COLUMNS = [
    "percentiles_is_in_top_1_percent",
    "percentiles_is_in_top_10_percent",
    "open_access_is_oa",
]

CATEGORICAL_COLUMNS = [
    "language",
    "type",
    "open_access_oa_status",
    "primary_location_display_name",
    "primary_location_host_organization_name",
]

COLUMN_MAPPINGS = [
    ("countries_codes", "country_first"),
    ("topics_field_display_name", "field_main"),
    ("topics_domain_display_name", "domain_main"),
]

ATLAS_COLUMNS = [
    "id",
    "title",
    "publication_year_cat",
    "apc_paid",
    "cited_by_count",
    "fwci",
    "percentiles_value",
    "percentiles_is_in_top_1_percent",
    "percentiles_is_in_top_10_percent",
    "open_access_is_oa",
    "open_access_oa_status",
    "language",
    "type",
    "primary_location_display_name",
    "country_first",
    "field_main",
    "domain_main",
    "text",
]

EMBEDDING_ATLAS_CMD = [
    "embedding-atlas",
    "--text",
    "text",
    "--enable-projection",
    "--auto-port",
]


def harvest_works(query: str, email: Optional[str] = None) -> list[dict]:
    """
    Harvest works from OpenAlex API based on the given query.
    Args:
        query: The OpenAlex query to search for.
        email: Optional email for the API polite tool.
        
    Returns:
        List of work dictionaries from OpenAlex.
    """
    client = OpenAlexClient(email=email)
    return client.list_all_works(
        filter=query,
        digest=True,
        abstract=True,
        per_page=50,
    )


def prepare_dataframe(works: list[dict]) -> pd.DataFrame:
    """
    Transform raw works data into a prepared DataFrame.
    Warning: only to work around CLI limitations for demonstration purposes
    
    Args:
        works: List of work dictionaries from OpenAlex.
        
    Returns:
        Prepared DataFrame ready for embedding atlas.
    """
    df = pd.DataFrame(works)
    
    # Create text column from title and abstract
    df["text"] = (
        df["title"].fillna("")
        + ". "
        + df["abstract"].fillna("").str.replace("No abstract available", " ", regex=False)
    )
    
    # Convert numeric columns
    for col in NUMERIC_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    
    #Force publication_year as string
    df["publication_year_cat"] = df["publication_year"].astype(str)
    
    # Convert boolean columns
    for col in BOOLEAN_COLUMNS:
        if col in df.columns:
            df[col] = df[col].astype("boolean")
    
    # Convert categorical columns
    for col in CATEGORICAL_COLUMNS:
        if col in df.columns:
            df[col] = df[col].astype("category")
    
    # Create derived columns from pipe-separated values
    for src, dst in COLUMN_MAPPINGS:
        if src in df.columns:
            df[dst] = (
                df[src]
                .str.split("|")
                .str[0]
                .astype("string")
            )
    
    # Select and return only columns needed for atlas
    available_cols = [col for col in ATLAS_COLUMNS if col in df.columns]
    return df[available_cols].reset_index(drop=True)


def run_embedding_atlas(data_path: Path) -> None:
    """
    Launch embedding-atlas dashboard with the given data file.
    
    Args:
        data_path: Path to the parquet file containing the data.
    """
    cmd = EMBEDDING_ATLAS_CMD + [str(data_path)]
    
    print(f"Running: {' '.join(cmd)}\n")
    
    proc = subprocess.Popen(cmd)
    print(f"Started embedding-atlas (pid={proc.pid}). Waiting for server to be ready...")
    
    try:
        proc.wait()
    except KeyboardInterrupt:
        print("\nStopping embedding-atlas...")
        proc.terminate()
        proc.wait()
        print("Stopped.")


def parse_arguments() -> argparse.Namespace:
    """
    Parse command-line arguments.
    
    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(
        description="Harvest OpenAlex works and display an embedding-atlas dashboard."
    )
    parser.add_argument(
        "--query",
        type=str,
        required=True,
        help="The OpenAlex query to search for.",
    )
    parser.add_argument(
        "--email",
        type=str,
        required=False,
        help="The email for the API polite tool.",
    )
    return parser.parse_args()


def main() -> None:
    """Main entry point for the application."""
    args = parse_arguments()
    
    print(f"Harvesting OpenAlex works for query: {args.query}")
    works = harvest_works(args.query, email=args.email)
    
    df_atlas = prepare_dataframe(works)
    
    # Write to a temporary parquet file
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".parquet", delete=False
    ) as tmp:
        df_atlas.to_parquet(tmp.name, index=False)
        tmp_path = Path(tmp.name)
    
    try:
        run_embedding_atlas(tmp_path)
    finally:
        # Clean up temp file
        tmp_path.unlink(missing_ok=True)
        print(f"Cleaned up temp file: {tmp_path}")


if __name__ == "__main__":
    main()