import io
import os
import zipfile

import pandas as pd
import streamlit as st

from converter import convert, read_conversies, read_nenbjerrum


@st.cache_data
def load_data():
    return read_conversies(), read_nenbjerrum()


st.set_page_config(page_title="Koppejan naar NEN Bjerrum", layout="wide")
st.title("Koppejan naar NEN Bjerrum")
st.write(
    "Upload een of meer D-Settlement sli bestanden. De gebruikte grondsoorten worden via de "
    "conversielijst omgezet naar zand, klei of veen en krijgen de RR, CR en Calpha waarden "
    "uit de iv infra rapportage. Het model wordt omgezet naar NEN - Bjerrum."
)

conversies, nenbjerrum = load_data()

uploaded_files = st.file_uploader(
    "SLI bestanden", type=["sli"], accept_multiple_files=True
)

if uploaded_files:
    results = []
    soils = []
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for uploaded_file in uploaded_files:
            content = uploaded_file.getvalue().decode("latin-1")
            converted, messages, converted_soils = convert(
                content, conversies, nenbjerrum
            )

            name = os.path.splitext(uploaded_file.name)[0]
            if converted is not None:
                zf.writestr(f"{name}.nb.sli", converted.encode("latin-1"))

            results.append(
                {
                    "bestand": uploaded_file.name,
                    "geconverteerd": converted is not None,
                    "meldingen": "\n".join(messages),
                }
            )
            for code, soil in converted_soils.items():
                soils.append(
                    {
                        "bestand": uploaded_file.name,
                        "grondsoort": code,
                        "nen bjerrum": soil["code"],
                        "RR": soil["rr"],
                        "CR": soil["cr"],
                        "Calpha": soil["calpha"],
                    }
                )

    num_converted = sum(r["geconverteerd"] for r in results)
    num_skipped = len(results) - num_converted

    if num_converted > 0:
        st.success(f"{num_converted} van de {len(results)} bestanden geconverteerd.")
    if num_skipped > 0:
        st.warning(
            f"{num_skipped} bestanden zijn overgeslagen omdat niet alle grondsoorten zijn omgezet."
        )

    st.download_button(
        "Download geconverteerde bestanden (zip)",
        data=zip_buffer.getvalue(),
        file_name="nen_bjerrum.zip",
        mime="application/zip",
        disabled=num_converted == 0,
    )

    st.subheader("Resultaat per bestand")
    st.dataframe(pd.DataFrame(results), hide_index=True, use_container_width=True)

    with st.expander("Omgezette grondsoorten"):
        st.dataframe(pd.DataFrame(soils), hide_index=True, use_container_width=True)
