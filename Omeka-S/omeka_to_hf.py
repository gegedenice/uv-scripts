#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "omeka-s-api-client @ git+https://github.com/gegedenice/omeka-s-api-client.git",
#   "uform",
#   "onnxruntime",
#   "usearch",
#   "datasets",
#   "huggingface_hub",
#   "pillow",
#   "requests",
#   "pandas",
#   "numpy",
#   "tqdm",
# ]
# ///

"""
Omeka S → UForm + USearch → Hugging Face dataset.

Usage (with uv):

    uv run omeka_to_hf.py \
        --collection-id 123 \
        --hf-repo your-username/your-dataset \
        --omeka-url https://humazur.univ-cotedazur.fr

Authentication can be passed via ENV:

    export OMEKA_URL="https://humazur.univ-cotedazur.fr"
    export OMEKA_IDENTITY="..."
    export OMEKA_CREDENTIAL="..."
    export HF_TOKEN="..."

or via CLI flags:
    --omeka-identity ... --omeka-credential ... --hf-token ...

Optional:
    --prefixes dcterms:identifier,dcterms:title,dcterms:subject

What it does:
  1. Fetch Omeka S items for the given collection (item set).
  2. Build a Pandas DataFrame and a Hugging Face Dataset and push it.
  3. Use only dcterms:title (Title) to build the text metadata for embeddings.
  4. Encode images + titles with UForm (multilingual base).
  5. Fuse image & text embeddings into a single vector per item.
  6. Build a USearch cosine index on fused embeddings.
  7. Save:
       - usearch_index.usearch
       - image_embeddings.fbin
       - text_embeddings.fbin
       - labels.npy
     and push them to the same HF dataset repo.
"""

from __future__ import annotations

import argparse
import logging
import os
from io import BytesIO
from typing import Any, Dict, List

import numpy as np
import pandas as pd
import requests
from datasets import Dataset
from huggingface_hub import HfApi, login
from PIL import Image
from tqdm import tqdm
from uform import Modality, get_model
from usearch.index import Index
from usearch.io import save_matrix

from omeka_s_api_client import OmekaSClient, OmekaSClientError


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


# ------------------------
# Helpers
# ------------------------


def reorder_columns(df: pd.DataFrame, cols_list: List[str], position: str = "first") -> pd.DataFrame:
    """Reorder DataFrame columns, moving cols_list either to front or end."""
    selected_columns = [col for col in cols_list if col in df.columns]
    remaining_columns = [col for col in df.columns if col not in selected_columns]

    if position == "first":
        new_column_order = selected_columns + remaining_columns
    elif position == "last":
        new_column_order = remaining_columns + selected_columns
    else:
        raise ValueError("position must be 'first' or 'last'")

    return df[new_column_order]


def field_to_str(value: Any) -> str:
    """Turn Omeka S field value (often list) into a readable string."""
    if value is None:
        return ""
    if isinstance(value, list):
        return "; ".join(str(v) for v in value)
    return str(value)


def parse_prefixes_arg(prefixes_arg: str | None) -> List[str] | None:
    """Parse --prefixes 'a,b,c' into a list ['a','b','c']."""
    if not prefixes_arg:
        return None
    return tuple(p.strip() for p in prefixes_arg.split(",") if p.strip())


def generate_dataset(
    client: OmekaSClient,
    item_set_id: int | None = None,
    prefixes: List[str] | None = None,
    per_page: int = 50,
) -> pd.DataFrame:
    """Fetch & parse Omeka S items for a given item set into a Pandas DataFrame."""
    logger.info("--- Fetching and parsing items from Omeka S collection ---")

    # If prefixes is None, fall back to the client's defaults
    if prefixes is None:
        prefixes = list(OmekaSClient._DEFAULT_PARSE_METADATA)

    logger.info("Using metadata prefixes: %s", prefixes)

    try:
        items_list = client.list_all_items(item_set_id=item_set_id, per_page=per_page)
        logger.info("Fetched %d raw items from Omeka S", len(items_list))

        parsed_items_list: List[Dict[str, Any]] = []

        for item_raw in tqdm(items_list, desc="Parsing items"):
            if "o:media" not in item_raw:
                continue

            parsed = OmekaSClient.digest_item_data(item_raw, prefixes=prefixes)
            if not parsed:
                continue

            # Attach image URLs
            medias_id = [m["o:id"] for m in item_raw.get("o:media", [])]
            medias_list: List[str] = []

            for media_id in medias_id:
                media = client.get_media(media_id)
                media_type = media.get("o:media_type", "")
                if isinstance(media_type, str) and "image" in media_type:
                    url = media.get("o:original_url")
                    if url:
                        medias_list.append(url)

            if not medias_list:
                continue

            parsed["images_urls"] = medias_list
            parsed_items_list.append(parsed)

        logger.info("Successfully parsed %d items with images", len(parsed_items_list))

        df = pd.DataFrame(parsed_items_list)
        logger.info("Resulting DataFrame has shape %s", df.shape)
        return df

    except OmekaSClientError as e:
        logger.error("Error fetching/parsing items from Omeka S: %s", e)
        raise
    except Exception as e:
        logger.exception("Unexpected error during Omeka S parsing: %s", e)
        raise


def build_items_for_embeddings(dataset: Dataset) -> List[Dict[str, Any]]:
    """
    Build simplified item dicts (label, meta_item, images) from HF dataset rows.

    Here we only use the dcterms:title field (mapped to "Title" column by digest_item_data),
    which is mandatory in Omeka S.
    """
    items: List[Dict[str, Any]] = []

    for row in tqdm(dataset, desc="Preparing items for embeddings"):
        item_id = row.get("item_id", None)
        if item_id is None:
            continue

        label = int(item_id)

        # Use only the mandatory dcterms:title (Title column)
        title = field_to_str(row.get("Title"))

        images_urls = row.get("images_urls", [])
        if isinstance(images_urls, str):
            images = [images_urls]
        elif isinstance(images_urls, list):
            images = [u for u in images_urls if isinstance(u, str)]
        else:
            images = []

        if not images:
            continue

        items.append({"label": label, "title": title, "images": images})

    logger.info("Prepared %d items with title+image for embedding", len(items))
    return items


def to_numpy_embedding(embedding: Any, ndim: int) -> np.ndarray:
    """Convert a UForm embedding to 1D float32 numpy vector of length ndim."""
    if hasattr(embedding, "detach"):
        arr = embedding.detach().cpu().numpy()
    else:
        arr = np.asarray(embedding)

    # Expect shape (1, D) or (D,)
    if arr.ndim == 2 and arr.shape[0] == 1:
        arr = arr[0]

    arr = arr.astype("float32")
    if arr.shape[0] < ndim:
        raise ValueError(f"Embedding dimension {arr.shape[0]} < requested NDIM {ndim}")
    return arr[:ndim]


def fuse_embeddings(img_vec: np.ndarray, txt_vec: np.ndarray, w_img: float = 0.5, w_txt: float = 0.5) -> np.ndarray:
    """L2-normalized weighted fusion of image and text embeddings."""
    img = img_vec / (np.linalg.norm(img_vec) + 1e-9)
    txt = txt_vec / (np.linalg.norm(txt_vec) + 1e-9)
    fused = w_img * img + w_txt * txt
    fused = fused / (np.linalg.norm(fused) + 1e-9)
    return fused.astype("float32")


# ------------------------
# Main pipeline
# ------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create UForm + USearch index from an Omeka S image collection and push to HF."
    )
    parser.add_argument("--collection-id", type=int, required=True, help="Omeka S item set ID (collection).")
    parser.add_argument("--hf-repo", type=str, required=True, help="Target Hugging Face dataset repo (e.g. user/my-dataset).")
    parser.add_argument("--hf-token", type=str, required=True, default=os.getenv("HF_TOKEN"), help="Hugging Face API with write permission.")
    parser.add_argument(
        "--omeka-url",
        type=str,
        default=os.getenv("OMEKA_URL", "https://humazur.univ-cotedazur.fr"),
        help="Omeka S base URL (default from OMEKA_URL env or humazur).",
    )
    parser.add_argument("--omeka-identity", type=str, default=os.getenv("OMEKA_IDENTITY"))
    parser.add_argument("--omeka-credential", type=str, default=os.getenv("OMEKA_CREDENTIAL")) 
    parser.add_argument("--per-page", type=int, default=50, help="Items per page when fetching from Omeka S.")
    parser.add_argument("--uform-model", type=str, default="unum-cloud/uform3-image-text-multilingual-base")
    parser.add_argument("--ndim", type=int, default=256, help="Embedding dimension to use for USearch (<= model dim).")
    parser.add_argument(
        "--prefixes",
        type=str,
        default=None,
        help=(
            "Comma-separated list of metadata prefixes/terms to parse from Omeka S, "
            "e.g. 'dcterms:identifier,dcterms:type,dcterms:title'. "
            "If omitted, uses OmekaSClient._DEFAULT_PARSE_METADATA."
        ),
    )

    args = parser.parse_args()

    if not args.omeka_identity or not args.omeka_credential:
        raise SystemExit(
            "Missing Omeka S credentials. Use --omeka-identity/--omeka-credential or env OMEKA_IDENTITY/OMEKA_CREDENTIAL."
        )

    if not args.hf_token:
        raise SystemExit("Missing HF token. Use --hf-token or env HF_TOKEN.")

    # Parse prefixes argument (if provided)
    prefixes_override = parse_prefixes_arg(args.prefixes)

    # --------------------
    # Login to HF
    # --------------------
    logger.info("Logging in to Hugging Face Hub...")
    login(token=args.hf_token)

    # --------------------
    # Init Omeka client
    # --------------------
    logger.info("Initializing Omeka S client...")
    client = OmekaSClient(
        args.omeka_url,
        args.omeka_identity,
        args.omeka_credential,
        default_per_page=args.per_page,
    )

    # --------------------
    # Fetch & build DataFrame
    # --------------------
    df = generate_dataset(
        client=client,
        item_set_id=args.collection_id,
        prefixes=prefixes_override,
        per_page=args.per_page,
    )

    # Add simple numeric id
    df["id"] = range(1, len(df) + 1)
    df = reorder_columns(df, ["id", "item_id", "Identifier", "images_urls", "Title"])

    # --------------------
    # Build and push HF Dataset
    # --------------------
    logger.info("Building Hugging Face Dataset from Pandas DataFrame...")
    hf_dataset = Dataset.from_pandas(df, preserve_index=False)

    logger.info("Pushing base metadata dataset to %s...", args.hf_repo)
    hf_dataset.push_to_hub(args.hf_repo, private=False)

    # --------------------
    # Prepare items for embeddings (only Title + images)
    # --------------------
    items = build_items_for_embeddings(hf_dataset)

    # --------------------
    # Load UForm model
    # --------------------
    logger.info("Loading UForm model: %s", args.uform_model)
    processors, models = get_model(args.uform_model, device="cpu")

    model_text = models[Modality.TEXT_ENCODER]
    model_image = models[Modality.IMAGE_ENCODER]
    processor_text = processors[Modality.TEXT_ENCODER]
    processor_image = processors[Modality.IMAGE_ENCODER]

    NDIM = args.ndim
    logger.info("Using embedding dimension NDIM=%d", NDIM)

    # --------------------
    # Build USearch index
    # --------------------
    logger.info("Initializing USearch index...")
    index = Index(
        ndim=NDIM,
        metric="cos",
        dtype="f32",
    )

    image_matrix: List[np.ndarray] = []
    text_matrix: List[np.ndarray] = []
    labels: List[int] = []

    logger.info("Encoding items with UForm and building fused index...")
    for item in tqdm(items, desc="Embedding items"):
        label = int(item["label"])
        title = item["title"]
        image_url = item["images"][0]  # first image only

        # Download image
        try:
            resp = requests.get(image_url, stream=True, timeout=30, verify=False)
            resp.raise_for_status()
            pil_img = Image.open(BytesIO(resp.content)).convert("RGB")
        except Exception as e:
            logger.warning("Failed to fetch image for label %s (%s): %s", label, image_url, e)
            continue

        # Encode image
        image_data = processor_image(pil_img)
        _, image_embedding = model_image.encode(image_data, return_features=True)
        img_vec = to_numpy_embedding(image_embedding, NDIM)

        # Encode text (title only)
        text_data = processor_text(title)
        _, text_embedding = model_text.encode(text_data, return_features=True)
        txt_vec = to_numpy_embedding(text_embedding, NDIM)

        fused_vec = fuse_embeddings(img_vec, txt_vec, w_img=0.5, w_txt=0.5)

        index.add(label, fused_vec, copy=True)

        labels.append(label)
        image_matrix.append(img_vec)
        text_matrix.append(txt_vec)

    if not labels:
        raise SystemExit("No items were successfully embedded; nothing to index.")

    image_matrix_arr = np.stack(image_matrix)
    text_matrix_arr = np.stack(text_matrix)
    labels_arr = np.asarray(labels, dtype=np.int64)

    # --------------------
    # Save index + matrices locally
    # --------------------
    logger.info("Saving USearch index and embedding matrices locally...")
    index_path = "usearch_index.usearch"
    img_fbin_path = "image_embeddings.fbin"
    txt_fbin_path = "text_embeddings.fbin"
    labels_path = "labels.npy"

    #index.save(index_path)
    #save_matrix(img_fbin_path, image_matrix_arr)
    #save_matrix(txt_fbin_path, text_matrix_arr)
    #np.save(labels_path, labels_arr)

    # --------------------
    # Upload artifacts to HF dataset repo
    # --------------------
    logger.info("Uploading USearch index and embedding matrices to %s...", args.hf_repo)
    api = HfApi()

    api.upload_file(
        path_or_fileobj=index,
        path_in_repo=index_path,
        repo_id=args.hf_repo,
        repo_type="dataset",
    )
    api.upload_file(
        path_or_fileobj=image_matrix_arr,
        path_in_repo=img_fbin_path,
        repo_id=args.hf_repo,
        repo_type="dataset",
    )
    api.upload_file(
        path_or_fileobj=text_matrix_arr,
        path_in_repo=txt_fbin_path,
        repo_id=args.hf_repo,
        repo_type="dataset",
    )
    api.upload_file(
        path_or_fileobj=labels_arr,
        path_in_repo=labels_path,
        repo_id=args.hf_repo,
        repo_type="dataset",
    )

    logger.info("All done! Dataset + USearch index + embeddings are in %s", args.hf_repo)


if __name__ == "__main__":
    main()