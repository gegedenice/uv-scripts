import re
import xml.etree.ElementTree as ET


PAIR_PATTERN = re.compile(
    r"\(\s*([0-9]{3})\s*,\s*([a-z0-9])(?:\s*,\s*([a-z0-9])\s*(=|~=)\s*([^)]+?)\s*)?\)"
)


def extract_field_robust(
    root: ET.Element,
    selectors: list[dict],
    get_all: bool = False,
    subfield_separator: str = " ",
):
    def matching_datafields(selector: dict) -> list[ET.Element]:
        tag = selector["tag"]
        filter_code = selector.get("filter_code")
        filter_op = selector.get("filter_op")
        filter_value = selector.get("filter_value")

        datafields = []
        for datafield in root.findall(f".//datafield[@tag='{tag}']"):
            if filter_code is not None:
                has_required_filter = False
                for sf in datafield.findall("./subfield"):
                    if sf.get("code") != filter_code:
                        continue
                    sf_text = (sf.text or "").strip()
                    if filter_op == "=" and sf_text == filter_value:
                        has_required_filter = True
                        break
                    if filter_op == "~=" and filter_value in sf_text:
                        has_required_filter = True
                        break
                if not has_required_filter:
                    continue
            datafields.append(datafield)

        return datafields

    def values_for_selector(selector: dict) -> list[str]:
        code = selector["code"]
        values = []
        for datafield in matching_datafields(selector):

            for subfield in datafield.findall(f"./subfield[@code='{code}']"):
                if subfield.text:
                    values.append(subfield.text.strip())
        return values

    if get_all:
        selector_groups: dict[tuple, list[dict]] = {}
        group_order: list[tuple] = []

        for selector in selectors:
            group_key = (
                selector["tag"],
                selector.get("filter_code"),
                selector.get("filter_op"),
                selector.get("filter_value"),
            )
            if group_key not in selector_groups:
                selector_groups[group_key] = []
                group_order.append(group_key)
            selector_groups[group_key].append(selector)

        values = []
        for group_key in group_order:
            grouped_selectors = selector_groups[group_key]
            if len(grouped_selectors) == 1:
                values.extend(values_for_selector(grouped_selectors[0]))
                continue

            for datafield in matching_datafields(grouped_selectors[0]):
                parts = []
                for selector in grouped_selectors:
                    code = selector["code"]
                    for subfield in datafield.findall(f"./subfield[@code='{code}']"):
                        if subfield.text and subfield.text.strip():
                            parts.append(subfield.text.strip())
                if parts:
                    values.append(subfield_separator.join(parts))

        return values

    for selector in selectors:
        selector_values = values_for_selector(selector)
        if selector_values:
            return selector_values[0]
    return None


def parse_mapping_line(raw_line: str) -> dict:
    raw_parts = raw_line.split("|", maxsplit=2)
    if len(raw_parts) != 3:
        raise ValueError(
            f"Invalid mapping '{raw_line}'. Expected format: Nom|(200,a),(200,b)|all:true"
        )

    field_name = raw_parts[0].strip()
    pairs_part = raw_parts[1].strip()
    all_part = raw_parts[2]
    if not field_name:
        raise ValueError(f"Invalid mapping '{raw_line}': field name is empty.")

    pair_matches = PAIR_PATTERN.findall(pairs_part)
    if not pair_matches:
        raise ValueError(
            f"Invalid mapping '{raw_line}': no (tag,code) pair found."
        )
    selectors = []
    for tag, code, filter_code, filter_op, filter_value in pair_matches:
        selectors.append(
            {
                "tag": tag.strip(),
                "code": code.strip(),
                "filter_code": filter_code.strip() if filter_code else None,
                "filter_op": filter_op.strip() if filter_op else None,
                "filter_value": filter_value.strip() if filter_value else None,
            }
        )

    option_parts = [part for part in all_part.split(";") if part.strip()]
    if not option_parts:
        raise ValueError(
            f"Invalid mapping '{raw_line}': third section must be all:true or all:false."
        )

    all_split = [part.strip() for part in option_parts[0].split(":", maxsplit=1)]
    if len(all_split) != 2 or all_split[0].lower() != "all":
        raise ValueError(
            f"Invalid mapping '{raw_line}': third section must start with all:true or all:false."
        )
    get_all = all_split[1].lower() in {"true", "1", "yes", "y"}

    separator = " "
    list_separator = " | "
    for option in option_parts[1:]:
        option_split = option.split(":", maxsplit=1)
        if len(option_split) != 2:
            raise ValueError(
                f"Invalid mapping '{raw_line}': malformed option '{option}'."
            )

        option_name = option_split[0].strip().lower()
        option_value = option_split[1]

        if option_name in {"sep", "separator"}:
            separator = bytes(option_value, "utf-8").decode("unicode_escape")
        elif option_name in {"list_sep", "list_separator"}:
            list_separator = bytes(option_value, "utf-8").decode("unicode_escape")
        else:
            raise ValueError(
                f"Invalid mapping '{raw_line}': unknown option '{option_name}'."
            )

    return {
        "field_name": field_name,
        "selectors": selectors,
        "get_all": get_all,
        "separator": separator,
        "list_separator": list_separator,
    }


def build_mappings(mapping_lines: list[str]) -> list[dict]:
    mappings = []
    for line in mapping_lines:
        clean = line.strip()
        if not clean:
            continue
        mappings.append(parse_mapping_line(clean))
    if not mappings:
        raise ValueError("No metadata mapping provided.")
    return mappings
