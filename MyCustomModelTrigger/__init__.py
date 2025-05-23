import azure.functions as func
import logging
import os
import json
import uuid
from datetime import datetime
from azure.core.credentials import AzureKeyCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.cosmos import CosmosClient, PartitionKey

# Document Intelligence
endpoint = os.environ["DOCUMENT_INTELLIGENCE_ENDPOINT"]
key = os.environ["DOCUMENT_INTELLIGENCE_KEY"]
model_id = os.environ["CUSTOM_MODEL_ID"]

# Cosmos DB
cosmos_endpoint = os.environ["COSMOS_ENDPOINT"]
cosmos_key = os.environ["COSMOS_KEY"]
cosmos_database = os.environ["COSMOS_DATABASE"]
cosmos_container = os.environ["COSMOS_CONTAINER"]

# Clients
doc_client = DocumentIntelligenceClient(endpoint=endpoint, credential=AzureKeyCredential(key))
cosmos_client = CosmosClient(cosmos_endpoint, cosmos_key)
database = cosmos_client.get_database_client(cosmos_database)
container = database.get_container_client(cosmos_container)

FACTEUR_TUNISIE = 0.58  # kg CO2/kWh

def main(myblob: func.InputStream):
    logging.info(f"Fichier reçu : {myblob.name}, taille : {myblob.length} octets")
    
    # Extraire l'ID utilisateur du chemin du blob (exemple: facture/user123/file.pdf)
    # Si tu n'as pas encore l'ID utilisateur dans le chemin, tu devras l'adapter
    path_parts = myblob.name.split('/')
    user_id = path_parts[1] if len(path_parts) > 1 else "default_user"
    
    # Analyse du document
    poller = doc_client.begin_analyze_document(
        model_id=model_id,
        body=myblob.read()
    )
    result = poller.result()
    
    # Préparer les données pour Cosmos DB
    extracted_data = {}
    total_kwh = None
    
    for doc in result.documents:
        logging.info("---- Résultats du modèle personnalisé ----")
        for name, field in doc.fields.items():
            value = getattr(field, "content", None) or "Aucune valeur"
            extracted_data[name] = value
            logging.info(f"{name} : {value}")

            # Extraction et conversion de la quantité d'électricité
    if "quantité électricité" in extracted_data:
        try:
            kwh_str = extracted_data["quantité électricité"].replace(",", ".").strip()
            total_kwh = float(kwh_str)
        except Exception as e:
            logging.error(f"Erreur conversion kWh : {e}")
            total_kwh = None
    else:
        logging.warning("Champ 'quantité électricité' non trouvé dans les données extraites.")

    # Calcul Scope 2
    scope2_kgco2 = total_kwh * FACTEUR_TUNISIE if total_kwh is not None else None
    
    # Créer le document pour Cosmos DB
    cosmos_item = {
        "id": str(uuid.uuid4()),
        "userId": user_id,  # Clé de partition
        "fileName": myblob.name,
        "processedDate": datetime.utcnow().isoformat(),
        "extractedData": extracted_data,
        "scope2": {
            "kwh": total_kwh,
            "kg_co2": round(scope2_kgco2, 2) if scope2_kgco2 is not None else None,
            "facteur": FACTEUR_TUNISIE,
            "date_calcul": datetime.utcnow().isoformat()
        }
    }
    
    # Sauvegarder dans Cosmos DB
    container.create_item(body=cosmos_item)
    logging.info(f"Données stockées dans Cosmos DB pour l'utilisateur {user_id}")
