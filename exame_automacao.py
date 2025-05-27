# -*- coding: utf-8 -*-
"""
Aplicação Streamlit para automação de pré‑laudos oftalmológicos
Autor: <Seu Nome>
"""

import os
import io
from datetime import datetime

import streamlit as st
from PIL import Image, ImageDraw, ImageFont

import openai
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

# ===================== CONFIGURAÇÕES ===================== #
# 1) Chave da OpenAI (defina como variável de ambiente ou coloque aqui)
openai.api_key = os.getenv("OPENAI_API_KEY", "SUA_CHAVE_OPENAI_AQUI")

# 2) Arquivo de credenciais de serviço do Google
SERVICE_ACCOUNT_FILE = "service_account.json"
SCOPES = ["https://www.googleapis.com/auth/drive"]

import json

def get_drive_service():
    """
    Autentica e retorna o serviço do Google Drive usando o JSON armazenado em
    st.secrets['GOOGLE_SERVICE_ACCOUNT_INFO'] ou variável de ambiente
    GOOGLE_SERVICE_ACCOUNT_INFO.
    """
    import streamlit as st
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    if "GOOGLE_SERVICE_ACCOUNT_INFO" in st.secrets:
        info = st.secrets["GOOGLE_SERVICE_ACCOUNT_INFO"]
    else:
        info = os.environ.get("GOOGLE_SERVICE_ACCOUNT_INFO")

    if not info:
        st.error("Credenciais do Google Drive não encontradas. Configure GOOGLE_SERVICE_ACCOUNT_INFO em Secrets.")
        st.stop()

    creds_dict = json.loads(info)
    credentials = service_account.Credentials.from_service_account_info(
        creds_dict, scopes=SCOPES
    )
    return build("drive", "v3", credentials=credentials)
auth/drive"]

# 3) IDs das pastas no Google Drive (crie-as antes e coloque os IDs)
FOLDER_IDS = {
    "OCT": "PASTA_ID_OCT",
    "Pentacam": "PASTA_ID_PENTACAM",
    "Retinografia": "PASTA_ID_RETINOGRAFIA",
    "Campo Visual": "PASTA_ID_CAMPO_VISUAL",
    "Ecografia": "PASTA_ID_ECOGRAFIA",
    "Exame Olho Seco CSO Antares": "PASTA_ID_ANTARES",
    "Mapa Epitelial": "PASTA_ID_MAPA_EPITELIAL",
    "VX130": "PASTA_ID_VX130",
}
# ========================================================= #

def get_drive_service():
    """Autentica e devolve serviço do Google Drive."""
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
    return build("drive", "v3", credentials=creds)

def upload_to_drive(service, file_bytes, filename, mimetype, folder_id):
    """Faz upload para o Google Drive e retorna o link público."""
    file_metadata = {"name": filename, "parents": [folder_id]}
    media = MediaIoBaseUpload(file_bytes, mimetype=mimetype, resumable=True)
    uploaded = (
        service.files()
        .create(body=file_metadata, media_body=media, fields="id, webViewLink")
        .execute()
    )
    # Torna o arquivo público
    service.permissions().create(
        fileId=uploaded["id"],
        body={"type": "anyone", "role": "reader"},
        fields="id",
    ).execute()
    return uploaded["webViewLink"]

def gerar_descricao_tecnica(image_b64, exam_type):
    """Envia a imagem para o GPT‑4o Vision e devolve descrição técnica."""
    response = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "Você é um assistente especializado em descrição técnica "
                    "de exames oftalmológicos. Descreva tecnicamente a imagem "
                    f"de um exame do tipo {exam_type} sem emitir diagnóstico."
                ),
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": "data:image/jpeg;base64," + image_b64
                        },
                    }
                ],
            },
        ],
        max_tokens=300,
    )
    return response.choices[0].message.content.strip()

def overlay_text_on_image(image, text):
    """Sobrepõe texto na imagem (rodapé)."""
    draw = ImageDraw.Draw(image)
    width, height = image.size
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 18)
    except IOError:
        font = ImageFont.load_default()
    margin = 10
    lines = text.split("\n")
    text_height = sum(font.getbbox(line)[3] - font.getbbox(line)[1] for line in lines)
    box_height = text_height + margin * 2
    draw.rectangle([(0, height - box_height), (width, height)], fill=(255, 255, 255, 200))
    y = height - box_height + margin
    for line in lines:
        draw.text((margin, y), line, fill=(0, 0, 0), font=font)
        y += font.getbbox(line)[3] - font.getbbox(line)[1]
    return image

def main():
    st.title("Automação de Pré‑Laudos Oftalmológicos")
    with st.form("upload_form"):
        nome_paciente = st.text_input("Nome completo do paciente *")
        tipo_exame = st.selectbox(
            "Tipo de exame *",
            [
                "OCT",
                "Pentacam",
                "Retinografia",
                "Campo Visual",
                "Ecografia",
                "Exame Olho Seco CSO Antares",
                "Mapa Epitelial",
                "VX130",
            ],
        )
        arquivo = st.file_uploader("Imagem ou PDF do exame *", type=["jpg", "jpeg", "png", "pdf"])
        enviado = st.form_submit_button("Enviar")

    if enviado:
        if not nome_paciente or not arquivo or not tipo_exame:
            st.error("Todos os campos são obrigatórios.")
            st.stop()

        data_str = datetime.now().strftime("%Y%m%d")
        nome_formatado = nome_paciente.strip().replace(" ", "_")
        extensao = os.path.splitext(arquivo.name)[1].lower()
        nome_arquivo = f"{nome_formatado}{data_str}{tipo_exame.replace(' ', '_')}{extensao}"

        drive_service = get_drive_service()
        folder_id = FOLDER_IDS[tipo_exame]

        file_bytes = io.BytesIO(arquivo.read())
        link_original = upload_to_drive(
            drive_service, file_bytes, nome_arquivo, arquivo.type, folder_id
        )

        descricao = "Descrição não gerada (arquivo PDF)."
        link_final = link_original

        if extensao in [".jpg", ".jpeg", ".png"]:
            import base64
            file_bytes.seek(0)
            encoded = base64.b64encode(file_bytes.read()).decode()
            descricao = gerar_descricao_tecnica(encoded, tipo_exame)

            file_bytes.seek(0)
            img = Image.open(file_bytes).convert("RGB")
            img_final = overlay_text_on_image(img, descricao)

            final_bytes = io.BytesIO()
            img_final.save(final_bytes, format="JPEG")
            final_bytes.seek(0)

            nome_final = nome_arquivo.replace(extensao, "_LAUDADO.jpg")
            link_final = upload_to_drive(
                drive_service, final_bytes, nome_final, "image/jpeg", folder_id
            )

        st.success("Exame enviado com sucesso!")
        st.markdown(f"**Arquivo original:** [{nome_arquivo}]({link_original})")
        if extensao in [".jpg", ".jpeg", ".png"]:
            st.markdown(f"**Imagem final:** [{nome_final}]({link_final})")
            with st.expander("Descrição técnica (pré‑laudo)"):
                st.write(descricao)

if __name__ == "__main__":
    main()
