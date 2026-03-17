import asyncio
import logging
import re
from amocrm_client import AmoCRMClient

logger = logging.getLogger("amocrm_dedup")

async def process_new_contact(new_contact_id: int, amocrm: AmoCRMClient):
    new_contact_data = await amocrm.get_contact(new_contact_id)
    if not new_contact_data:
        return

    phone = extract_phone(new_contact_data)
    tg_nick = extract_tg_nick(new_contact_data)

    if not phone and not tg_nick:
        return

    search_query = phone if phone else tg_nick
    duplicates = await amocrm.search_contact_by_query(search_query)

    if not duplicates:
        return

    old_contacts = [c for c in duplicates if c["id"] != new_contact_id and "ДУБЛЬ" not in str(c.get("name", "")).upper()]
    if not old_contacts:
        return

    old_contacts.sort(key=lambda x: x["created_at"])
    base_contact_id = old_contacts[0]["id"]

    logger.info(f"Склейка: переносим данные в контакт {base_contact_id}")

    await amocrm.update_contact(base_contact_id, new_contact_data)
    await amocrm.transfer_notes(from_id=new_contact_id, to_id=base_contact_id)
    await asyncio.sleep(2)
    await amocrm.transfer_deals(from_id=new_contact_id, to_id=base_contact_id)
    await amocrm.delete_contact(new_contact_id)

def extract_phone(contact_data: dict) -> str | None:
    custom_fields = contact_data.get("custom_fields_values")
    if not custom_fields:
        return None
    for field in custom_fields:
        if field.get("field_code") == "PHONE":
            values = field.get("values")
            if values and len(values) > 0:
                raw_phone = str(values[0].get("value", ""))
                clean_phone = re.sub(r'\D', '', raw_phone)
                return clean_phone if clean_phone else None
    return None

def extract_tg_nick(contact_data: dict) -> str | None:
    custom_fields = contact_data.get("custom_fields_values")
    if not custom_fields:
        return None
        
    for field in custom_fields:
        # Ищем системное поле Должности по коду
        if field.get("field_code") == "POSITION":
            values = field.get("values")
            if values and len(values) > 0:
                raw_nick = str(values[0].get("value", ""))
                # Убираем символ @ на случай, если кто-то ввел его руками
                clean_nick = raw_nick.replace("@", "").strip()
                return clean_nick if clean_nick else None
                
    return None