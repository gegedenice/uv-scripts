import pandas as pd
from typing import Literal
from func_to_web.types import FileResponse, TextFile

from common.exports import build_exports
from common.mappings import build_mappings, extract_field_robust
from common.openalex import call_openalex, create_openalex_client
from common.ppn import fetch_ppn_xml, read_ppns_from_file
from common.sru import fetch_sru_records


def build_dataframe(ppns: list[str], mappings: list[dict]) -> pd.DataFrame:
    if not ppns:
        raise ValueError("No PPN found in the uploaded file.")

    rows = []
    for ppn in ppns:
        row = {"PPN": ppn}
        try:
            root = fetch_ppn_xml(ppn)
        except Exception as exc:
            row["error"] = str(exc)
            for mapping in mappings:
                row[mapping["field_name"]] = None
            rows.append(row)
            continue

        for mapping in mappings:
            value = extract_field_robust(
                root=root,
                selectors=mapping["selectors"],
                get_all=mapping["get_all"],
                subfield_separator=mapping["separator"],
            )
            if isinstance(value, list):
                row[mapping["field_name"]] = mapping["list_separator"].join(value)
            else:
                row[mapping["field_name"]] = value
        rows.append(row)

    return pd.DataFrame(rows)


def build_dataframe_from_sru_records(records: list, mappings: list[dict]) -> pd.DataFrame:
    rows = []
    for idx, root in enumerate(records, start=1):
        ppn_el = root.find(".//controlfield[@tag='001']")
        ppn = (ppn_el.text or "").strip() if ppn_el is not None and ppn_el.text else None
        row = {"record_index": idx, "PPN": ppn}

        for mapping in mappings:
            value = extract_field_robust(
                root=root,
                selectors=mapping["selectors"],
                get_all=mapping["get_all"],
                subfield_separator=mapping["separator"],
            )
            if isinstance(value, list):
                row[mapping["field_name"]] = mapping["list_separator"].join(value)
            else:
                row[mapping["field_name"]] = value

        rows.append(row)

    return pd.DataFrame(rows)


def normalize_openalex_result_to_dataframe(result) -> pd.DataFrame:
    if isinstance(result, pd.DataFrame):
        return result

    if isinstance(result, dict):
        if "results" in result and isinstance(result["results"], list):
            rows = result["results"]
            if rows and isinstance(rows[0], dict):
                return pd.json_normalize(rows)
            return pd.DataFrame({"value": rows})
        return pd.json_normalize([result])

    if isinstance(result, list):
        if len(result) == 0:
            return pd.DataFrame()
        if isinstance(result[0], dict):
            return pd.json_normalize(result)
        return pd.DataFrame({"value": result})

    return pd.DataFrame([{"value": result}])


def harvest_sudoc_metadata_from_ppn_list(
    ppn_file: TextFile,
    metadata_mappings: list[str] = [
        "Titre|(200,a)|all:false",
        "Premier Auteur|(200,f)|all:false",
        "Autres auteurs|(200,g)|all:true",
    ],
) -> tuple[pd.DataFrame, FileResponse, FileResponse, FileResponse]:
    """
    ### Extraire des metadonnees a partir d'un fichier de PPN

    **Description :**
    Deposez un fichier `.txt` contenant un PPN par ligne afin d'extraire des
    metadonnees bibliographiques depuis les notices Sudoc correspondantes.

    **Parametres :**
    - `ppn_file` : fichier texte contenant un PPN par ligne.
    - `metadata_mappings` : liste des regles d'extraction.

      **Syntaxe generale :**
      - `NomChamp|(Zone,sous-zone)|all:false`
      - `NomChamp|(Zone,sous-zone)|all:true`
      - `NomChamp|(Zone,sous-zone),(Zone,sous-zone)|all:true;sep: `
      - `NomChamp|(Zone,sous-zone),(Zone,sous-zone)|all:true;sep: ;list_sep:/`

      **Signification des options :**
      - `all:false` : renvoie la premiere valeur trouvee.
      - `all:true` : collecte toutes les occurrences correspondantes.
      - `sep:...` ou `separator:...` : separateur utilise entre plusieurs
        sous-zones selectionnees dans une meme occurrence MARC.
      - `list_sep:...` ou `list_separator:...` : separateur utilise entre
        plusieurs occurrences MARC.

      **Valeurs par defaut :**
      - sans `sep`, les sous-zones d'une meme occurrence sont jointes par un espace ;
      - sans `list_sep`, les occurrences sont jointes par ` | `.

      **Exemples :**
      - `Titre|(200,a)|all:false`
      - `Premier Auteur|(200,f)|all:false`
      - `Autres auteurs|(200,g)|all:true`
      - `Titre complet|(200,b),(200,c)|all:true;sep: `
      - `Membres|(701,b,4=555),(701,a,4=555)|all:true;sep: `
      - `Membres|(701,b,4=555),(701,a,4=555)|all:true;sep: ;list_sep:/`

      **Exemple de resultat :**
      - `Membres|(701,b,4=555),(701,a,4=555)|all:true;sep: `
        produit `Michel Bouvier | Sebastien Jeannard`

      **Filtres conditionnels :**
      - `=` pour une correspondance exacte :
        `Auteur principal|(700,a,4=070)|all:true`
      - `~=` pour une correspondance partielle :
        `Auteur principal|(700,a,4~=07)|all:true`

    **Retour :**
    - Un tuple contenant :
      1. un `DataFrame` pandas avec les metadonnees extraites ;
      2. un export `CSV` ;
      3. un export `XLSX` ;
      4. un export `JSON`.
    """
    ppns = read_ppns_from_file(ppn_file)
    mappings = build_mappings(metadata_mappings)
    df = build_dataframe(ppns=ppns, mappings=mappings)
    csv_file, xlsx_file, json_file = build_exports(df, filename_prefix="ppn_metadata")
    return df, csv_file, xlsx_file, json_file


def harvest_sudoc_metadata_from_sru(
    query: str = "tdo=y",
    metadata_mappings: list[str] = [
        "Titre|(200,a)|all:false",
        "Premier Auteur|(200,f)|all:false",
        "Autres auteurs|(200,g)|all:true",
    ],
    batch_size: int = 25,
) -> tuple[pd.DataFrame, FileResponse, FileResponse, FileResponse]:
    """
    ### Extraire des metadonnees a partir d'une requete SRU Sudoc

    **Description :**
    Execute une requete SRU Sudoc, recupere toutes les notices retournees,
    puis extrait les champs souhaites selon les regles fournies.

    **Parametres :**
    - `query` : requete SRU Sudoc, par exemple `tdo=y` ou
      `nth="Paris, ENMP" tdo=y apu>=2024`.
    - `metadata_mappings` : liste des regles d'extraction.

      **Syntaxe generale :**
      - `NomChamp|(Zone,sous-zone)|all:false`
      - `NomChamp|(Zone,sous-zone)|all:true`
      - `NomChamp|(Zone,sous-zone),(Zone,sous-zone)|all:true;sep: `
      - `NomChamp|(Zone,sous-zone),(Zone,sous-zone)|all:true;sep: ;list_sep:/`

      **Signification des options :**
      - `all:false` : renvoie la premiere valeur trouvee.
      - `all:true` : collecte toutes les occurrences correspondantes.
      - `sep:...` ou `separator:...` : separateur utilise entre plusieurs
        sous-zones selectionnees dans une meme occurrence MARC.
      - `list_sep:...` ou `list_separator:...` : separateur utilise entre
        plusieurs occurrences MARC.

      **Valeurs par defaut :**
      - sans `sep`, les sous-zones d'une meme occurrence sont jointes par un espace ;
      - sans `list_sep`, les occurrences sont jointes par ` | `.

      **Exemples :**
      - `Titre|(200,b),(200,c)|all:true`
      - `Auteur principal|(700,a,4=070)|all:true`
      - `Titre|(200,b),(200,c)|all:true;sep: `
      - `Membres|(701,b,4=555),(701,a,4=555)|all:true;sep: `
      - `Membres|(701,b,4=555),(701,a,4=555)|all:true;sep: ;list_sep:/`
    - `batch_size` : nombre de notices recuperees par lot. Valeur par defaut : `25`.

      **Filtres conditionnels :**
      - `=` pour une correspondance exacte :
        `Auteur principal|(700,a,4=070)|all:true`
      - `~=` pour une correspondance partielle :
        `Auteur principal|(700,a,4~=07)|all:true`

    **Retour :**
    - Un tuple contenant :
      1. un `DataFrame` pandas avec les metadonnees extraites ;
      2. un export `CSV` ;
      3. un export `XLSX` ;
      4. un export `JSON`.
    """
    clean_query = query.strip()
    if not clean_query:
        raise ValueError("Query is empty.")

    mappings = build_mappings(metadata_mappings)
    records = fetch_sru_records(query=clean_query, batch_size=batch_size)
    if not records:
        raise ValueError("No records returned by SRU for this query.")

    df = build_dataframe_from_sru_records(records=records, mappings=mappings)
    csv_file, xlsx_file, json_file = build_exports(df, filename_prefix="sru_metadata")
    return df, csv_file, xlsx_file, json_file


def harvest_entities_metadata_from_openalex(
    entity_id: str | None = None,
    api_key: str = "",
    method_type: Literal["count", "get", "list", "list_all"] = "list",
    entity: Literal[
        "work",
        "author",
        "institution",
        "source",
        "publisher",
        "topic",
        "funder",
        "concept",
    ] = "work",
    filter_value: str | None = None,
    sort: str | None = None,
    digest: bool = False,
    abstract: bool = False,
    per_page: int = 25,
) -> tuple[pd.DataFrame, FileResponse, FileResponse, FileResponse]:
    """
    ### Extraire des donnees depuis OpenAlex

    **Description :**
    Interroge OpenAlex via `openalex-api-client` afin de recuperer des
    metadonnees bibliographiques ou des entites de reference, puis produit
    un apercu tabulaire et des exports telechargeables.

    **Parametres :**
    - `entity_id` : identifiant OpenAlex (par exemple `W...`, `A...`, `I...`).
      Obligatoire pour la methode `get`.
    - `api_key` : cle API OpenAlex optionnelle pour beneficier de limites plus elevees.
    - `method_type` : type de requete a executer :
      - `get` : recupere une entite unique par identifiant ;
      - `list` : liste des entites avec filtres optionnels ;
      - `list_all` : liste complete paginee ;
      - `count` : compte les entites correspondant aux criteres.
    - `entity` : type d'entite OpenAlex a interroger :
      - `work`, `author`, `institution`, `source`, `publisher`, `topic`, `funder`, `concept`.
    - `filter_value` : chaine de filtres OpenAlex
      (ex. `authorships.author.id:A1234567890`, `publication_year:2020,is_oa:true`).
    - `sort` : critere de tri OpenAlex (ex. `publication_year:desc`).
    - `digest` : inclut les informations de synthese lorsque l'endpoint les prend en charge.
    - `abstract` : inclut le resume lorsque l'endpoint le permet.
    - `per_page` : nombre de resultats par page. Valeur par defaut : `25`.

    **Retour :**
    - Un tuple contenant :
      1. un `DataFrame` pandas avec les donnees recuperees ;
      2. un export `CSV` ;
      3. un export `XLSX` ;
      4. un export `JSON`.

    **Exemples :**
    - Recuperer les travaux d'un auteur :
      `filter_value="authorships.author.id:A1234567890"`
    - Recuperer les travaux publies en 2020 :
      `filter_value="publication_year:2020"`
    """
    client = create_openalex_client(
        api_key=api_key.strip() or None,
        default_per_page=per_page,
    )
    result = call_openalex(
        client=client,
        method_type=method_type,
        entity=entity,
        entity_id=entity_id,
        filter_value=filter_value,
        sort=sort,
        digest=digest,
        abstract=abstract,
        per_page=per_page,
    )
    df = normalize_openalex_result_to_dataframe(result)
    csv_file, xlsx_file, json_file = build_exports(df, filename_prefix="openalex_metadata")
    return df, csv_file, xlsx_file, json_file
