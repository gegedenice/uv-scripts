# biblio-tools

[English version](./README.md)

`biblio-tools` est une petite application Python qui expose des utilitaires de collecte bibliographique via une interface `func-to-web`.

Elle prend actuellement en charge trois workflows :

- Extraire des métadonnées à partir d'un fichier texte contenant des PPN Sudoc
- Extraire des métadonnées à partir d'une requête SRU Sudoc
- Récupérer des entités depuis OpenAlex et exporter les résultats

L'application renvoie un tableau d'aperçu ainsi que des fichiers `CSV`, `XLSX` et `JSON` téléchargeables pour chaque workflow.

## Fonctionnalités

- Interface web simple propulsée par `func-to-web`
- Extraction de métadonnées depuis des notices Sudoc XML / UNIMARC
- Règles de mapping configurables pour l'extraction des notices Sudoc
- Interrogation d'OpenAlex avec `get`, `list`, `list_all` et `count`
- Génération d'exports `CSV`, `XLSX` et `JSON`

## Structure du projet

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

## Prérequis

- Python 3.11+
- `uv`
- Accès réseau vers :
  - `https://www.sudoc.fr`
  - `https://sudoc.abes.fr`
  - les endpoints OpenAlex utilisés par `openalex-api-client`

Les dépendances sont déclarées directement dans [main.py](/home/root/PythonApps/biblio-tools/main.py).

## Lancer l'application

Depuis la racine du projet :

```bash
UV_CACHE_DIR=/root/.cache/uv uv run main.py
```

L'en-tête de script de [main.py](/home/root/PythonApps/biblio-tools/main.py) permet à `uv` de résoudre automatiquement les dépendances nécessaires.

Au démarrage, l'interface expose deux groupes :

- `Sudoc`
  - `harvest_sudoc_metadata_from_ppn_list`
  - `harvest_sudoc_metadata_from_sru`
- `OpenAlex`
  - `harvest_entities_metadata_from_openalex`

## Workflows

### 1. Extraire des métadonnées à partir d'un fichier de PPN

Point d'entrée : [src/harvest_tools.py](/home/root/PythonApps/biblio-tools/src/harvest_tools.py)

Utilisez `harvest_sudoc_metadata_from_ppn_list` pour déposer un fichier texte contenant un PPN par ligne.

Déroulé du traitement :

1. Le fichier est lu puis dédupliqué
2. Chaque PPN est récupéré depuis `https://www.sudoc.fr/<PPN>.xml`
3. Les champs de métadonnées configurés sont extraits du XML renvoyé
4. Les résultats sont assemblés dans un dataframe puis exportés

Mappings par défaut :

```text
Titre|(200,a)|all:false
Premier Auteur|(200,f)|all:false
Autres auteurs|(200,g)|all:true
```

### 2. Extraire des métadonnées à partir d'une requête SRU Sudoc

Point d'entrée : [src/harvest_tools.py](/home/root/PythonApps/biblio-tools/src/harvest_tools.py)

Utilisez `harvest_sudoc_metadata_from_sru` pour exécuter une requête SRU Sudoc, paginer sur l'ensemble des résultats, extraire les métadonnées UNIMARC et exporter le jeu de données.

Paramètres importants :

- `query` : une chaîne de requête SRU Sudoc stricte
- `metadata_mappings` : règles d'extraction utilisant la même syntaxe que dans le workflow PPN
- `batch_size` : nombre de notices récupérées par requête SRU

Exemple de requête :

```text
tdo=y
```

L'implémentation SRU se trouve dans [common/sru.py](/home/root/PythonApps/biblio-tools/common/sru.py).

### 3. Récupérer des données depuis OpenAlex

Point d'entrée : [src/harvest_tools.py](/home/root/PythonApps/biblio-tools/src/harvest_tools.py)

Utilisez `harvest_entities_metadata_from_openalex` pour interroger OpenAlex via `openalex-api-client`.

Paramètres pris en charge :

- `method_type` : `count`, `get`, `list`, `list_all`
- `entity` : `work`, `author`, `institution`, `source`, `publisher`, `topic`, `funder`, `concept`
- `entity_id` : requis pour `get`
- `filter_value` : chaîne de filtres OpenAlex
- `sort` : critère de tri OpenAlex
- `digest` : transmis lorsque pris en charge
- `abstract` : transmis pour les endpoints `work` lorsque pris en charge
- `per_page` : taille de page pour les requêtes de liste
- `api_key` : clé API OpenAlex optionnelle

Exemples :

```text
method_type="get", entity="work", entity_id="W1234567890"
filter_value="publication_year:2024"
filter_value="authorships.author.id:A1234567890"
sort="publication_year:desc"
```

L'initialisation du client OpenAlex et la gestion de compatibilité associée se trouvent dans [common/openalex.py](/home/root/PythonApps/biblio-tools/common/openalex.py).

## Syntaxe des mappings de métadonnées

Les règles d'extraction Sudoc sont interprétées par [common/mappings.py](/home/root/PythonApps/biblio-tools/common/mappings.py).

Chaque chaîne de mapping suit ce format :

```text
FieldName|(MARCField,Subfield)|all:true
FieldName|(MARCField,Subfield)|all:false
FieldName|(MARCField,Subfield)|all:true;sep: / 
FieldName|(MARCField,Subfield)|all:true;sep: ;list_sep: | 
```

En pratique, le troisième segment doit être écrit ainsi :

```text
FieldName|(200,a)|all:false
FieldName|(700,a)|all:true
```

Vous pouvez également fournir plusieurs sélecteurs :

```text
Titre complet|(200,a),(200,e)|all:true
Titre complet|(200,b),(200,c)|all:true;sep: 
Titre complet|(200,b),(200,c)|all:true;sep: / 
Members|(701,b,4=555),(701,a,4=555)|all:true;sep: 
```

Les filtres conditionnels sont pris en charge sur un même champ :

```text
Auteur principal|(700,a,4=070)|all:true
Auteur partiel|(700,a,4~=07)|all:true
```

Comportement :

- `all:false` : renvoie la première valeur trouvée parmi les sélecteurs
- `all:true` : collecte toutes les valeurs correspondantes parmi les sélecteurs
- Lorsque plusieurs sélecteurs partagent le même champ MARC et le même filtre, les sous-zones correspondantes sont d'abord combinées à l'intérieur de chaque occurrence de champ
- `sep:...` ou `separator:...` : séparateur utilisé à l'intérieur d'une occurrence de champ lorsque plusieurs sous-zones sélectionnées sont combinées
- `list_sep:...` ou `list_separator:...` : séparateur utilisé entre plusieurs occurrences d'un même champ
- si aucun `sep` n'est fourni, les sous-zones à l'intérieur d'une occurrence sont jointes par un espace simple
- si aucun `list_sep` n'est fourni, les occurrences répétées sont jointes par ` | ` avant export

Notes :

- Exemple :
  `Members|(701,b,4=555),(701,a,4=555)|all:true;sep: `
  renvoie `Michel Bouvier | Sébastien Jeannard`
- Pour changer également le séparateur externe :
  `Members|(701,b,4=555),(701,a,4=555)|all:true;sep: ;list_sep:/`
  renvoie `Michel Bouvier/Sébastien Jeannard`
- Les séquences d'échappement sont prises en charge pour les deux séparateurs, par exemple :
  `sep:\n` pour un saut de ligne ou `sep:\t` pour une tabulation

## Fichiers de sortie

Tous les workflows renvoient :

- un dataframe pandas pour l'aperçu dans l'interface
- `<prefix>.csv`
- `<prefix>.xlsx`
- `<prefix>.json`

La génération des exports est implémentée dans [common/exports.py](/home/root/PythonApps/biblio-tools/common/exports.py).

Préfixes de fichiers actuels :

- `ppn_metadata`
- `sru_metadata`
- `openalex_metadata`

## Conception interne

### `main.py`

Enregistre les outils disponibles auprès de `func-to-web`.

### `src/harvest_tools.py`

Contient les fonctions de workflow exposées à l'utilisateur et la logique de normalisation des dataframes.

### `common/ppn.py`

Récupère les notices XML Sudoc par PPN et lit les fichiers de PPN déposés.

### `common/sru.py`

Appelle l'endpoint SRU Sudoc, compte les résultats, pagine et extrait les notices UNIMARC embarquées.

### `common/mappings.py`

Analyse les définitions de mapping et extrait les valeurs depuis le XML UNIMARC.

### `common/openalex.py`

Crée le client OpenAlex et s'adapte à de petites différences de signature de l'API.

### `common/exports.py`

Construit les exports `CSV`, `XLSX` et `JSON` téléchargeables à partir de dataframes pandas.

## Notes et limitations

- Il n'y a pas de `pyproject.toml` ; la gestion des dépendances repose actuellement sur les métadonnées de script `uv` inline dans [main.py](/home/root/PythonApps/biblio-tools/main.py).
- Les erreurs réseau sont remontées directement depuis `requests` ou les exceptions client.
- L'encodage des requêtes Sudoc est actuellement géré manuellement dans [common/sru.py](/home/root/PythonApps/biblio-tools/common/sru.py), ce qui peut être fragile pour des requêtes SRU plus complexes.
- Pour OpenAlex, `count` délègue actuellement à l'aide de comptage du client sans transmettre la chaîne de filtre fournie ; si des comptages filtrés sont nécessaires, cette implémentation doit être revue dans [common/openalex.py](/home/root/PythonApps/biblio-tools/common/openalex.py).

## Exemples de démarrage rapide

### Lancement

```bash
UV_CACHE_DIR=/root/.cache/uv uv run main.py
```

### Exemple de fichier PPN

```text
123456789
987654321
```

### Exemples de mappings

```text
Titre|(200,a)|all:false
Sous-titre|(200,e)|all:false
Auteur principal|(700,a,4=070)|all:true
```
