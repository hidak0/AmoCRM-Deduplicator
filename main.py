from fastapi import FastAPI, Request, BackgroundTasks
import logging
import os
from services import process_new_contact
from amocrm_client import AmoCRMClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("amocrm_dedup")

app = FastAPI()

amocrm = AmoCRMClient(
    base_url=os.getenv("AMOCRM_BASE_URL"),
    access_token=os.getenv("AMOCRM_ACCESS_TOKEN")
)

@app.post("/webhook/contact-added")
async def contact_added_webhook(request: Request, background_tasks: BackgroundTasks):
    form_data = await request.form()
    contact_id_str = form_data.get("contacts[add][0][id]")
    
    if contact_id_str:
        background_tasks.add_task(process_new_contact, int(contact_id_str), amocrm)
    
    return {"status": "success"}

@app.get("/health")
async def health_check():
    return {"status": "ok"}