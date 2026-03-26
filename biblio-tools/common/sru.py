import xml.etree.ElementTree as ET

import requests


SRU_BASE_URL = "https://sudoc.abes.fr/cbs/sru/"
SRU_NAMESPACES = {"srw": "http://www.loc.gov/zing/srw/"}


def _parse_xml(content: bytes) -> ET.Element:
    return ET.fromstring(content.decode("utf-8"))


def _extract_unimarc_record(record_data_el: ET.Element) -> ET.Element | None:
    for elem in record_data_el.iter():
        local_name = elem.tag.split("}", 1)[-1]
        if local_name == "record":
            has_marc_children = any(
                child.tag.split("}", 1)[-1] in {"datafield", "controlfield"}
                for child in elem.iter()
            )
            if has_marc_children:
                return elem
    return None


def get_sru_number_of_records(query: str) -> int:
    encoded_query = (
        query.replace(" and ", "+")
        .replace(" ", "%20")
        .replace("=", "%3D")
        .replace('"', "%22")
    )
    params = {
        "operation": "searchRetrieve",
        "version": "1.1",
        "recordSchema": "unimarc",
        "maximumRecords": 1,
        "startRecord": 1,
    }
    query_string = "&".join([f"{key}={value}" for key, value in params.items()])
    final_url = f"{SRU_BASE_URL}?{query_string}&query={encoded_query}"
    print(final_url)
    response = requests.get(final_url, timeout=30)
    response.raise_for_status()
    root = _parse_xml(response.content)
    number_el = root.find(".//srw:numberOfRecords", namespaces=SRU_NAMESPACES)
    return int(number_el.text) if number_el is not None and number_el.text else 0


def fetch_sru_records(query: str, batch_size: int = 25) -> list[ET.Element]:
    if batch_size <= 0:
        raise ValueError("batch_size must be > 0")

    encoded_query = (
        query.replace(" and ", "+")
        .replace(" ", "%20")
        .replace("=", "%3D")
        .replace('"', "%22")
    )
    total = get_sru_number_of_records(query)
    records = []

    for start in range(1, total + 1, batch_size):
        params = {
            "operation": "searchRetrieve",
            "version": "1.1",
            "recordSchema": "unimarc",
            "maximumRecords": batch_size,
            "startRecord": start,
        }
        query_string = "&".join([f"{key}={value}" for key, value in params.items()])
        final_url = f"{SRU_BASE_URL}?{query_string}&query={encoded_query}"
        response = requests.get(final_url, timeout=60)
        response.raise_for_status()
        root = _parse_xml(response.content)

        for record_el in root.findall(".//srw:record", namespaces=SRU_NAMESPACES):
            record_data_el = record_el.find("./srw:recordData", namespaces=SRU_NAMESPACES)
            if record_data_el is None:
                continue
            unimarc_record = _extract_unimarc_record(record_data_el)
            if unimarc_record is not None:
                records.append(unimarc_record)

    return records
