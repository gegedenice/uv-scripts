from io import BytesIO

import pandas as pd
from func_to_web.types import FileResponse


def build_exports(
    df: pd.DataFrame,
    filename_prefix: str = "ppn_metadata",
) -> tuple[FileResponse, FileResponse, FileResponse]:
    csv_bytes = df.to_csv(index=False).encode("utf-8")

    xlsx_buffer = BytesIO()
    with pd.ExcelWriter(xlsx_buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="metadata")
    xlsx_bytes = xlsx_buffer.getvalue()

    json_bytes = df.to_json(orient="records", force_ascii=False, indent=2).encode("utf-8")

    return (
        FileResponse(data=csv_bytes, filename=f"{filename_prefix}.csv"),
        FileResponse(data=xlsx_bytes, filename=f"{filename_prefix}.xlsx"),
        FileResponse(data=json_bytes, filename=f"{filename_prefix}.json"),
    )
