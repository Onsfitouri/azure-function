import azure.functions as func
import logging
import os
from azure.core.credentials import AzureKeyCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient

# Charger les variables d'environnement
endpoint = os.environ["DOCUMENT_INTELLIGENCE_ENDPOINT"]
key = os.environ["DOCUMENT_INTELLIGENCE_KEY"]
model_id = os.environ["CUSTOM_MODEL_ID"]

client = DocumentIntelligenceClient(endpoint=endpoint, credential=AzureKeyCredential(key))

def main(myblob: func.InputStream):
    logging.info(f"Fichier reçu : {myblob.name}, taille : {myblob.length} octets")

    # Analyse du document via modèle personnalisé
    poller = client.begin_analyze_document(
        model_id=model_id,
         body=myblob.read()
    )
    result = poller.result()

    for doc in result.documents:
        logging.info("---- Résultats du modèle personnalisé ----")
        for name, field in doc.fields.items():
            value = getattr(field, "content", None) or "Aucune valeur"
            logging.info(f"{name} : {value}")
