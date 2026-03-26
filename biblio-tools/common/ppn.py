import xml.etree.ElementTree as ET

import requests
from func_to_web.types import TextFile


def fetch_ppn_xml(ppn: str) -> ET.Element:
    url = f"https://www.sudoc.fr/{ppn}.xml"
    response = requests.get(url, headers={"Accept": "application/xml"}, timeout=20)
    response.raise_for_status()
    return ET.fromstring(response.content.decode("utf-8"))


def read_ppns_from_file(ppn_file: TextFile) -> list[str]:
    ppns = []
    with open(ppn_file, "r", encoding="utf-8") as file:
        for line in file:
            ppn = line.strip()
            if ppn and ppn not in ppns:
                ppns.append(ppn)
    return ppns

