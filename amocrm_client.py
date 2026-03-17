import httpx
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger("amocrm_dedup")

class AmoCRMClient:
    def __init__(self, base_url: str, access_token: str):
        self.base_url = base_url.rstrip('/')
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

    async def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        url = f"{self.base_url}/api/v4/{endpoint}"
        async with httpx.AsyncClient() as client:
            response = await client.request(method, url, headers=self.headers, **kwargs)
            if response.status_code >= 400:
                logger.error(f"AmoCRM API Error: {response.status_code} - {response.text}")
                response.raise_for_status()
            if response.status_code == 204:
                return {}
            return response.json()

    async def search_contact_by_query(self, query: str) -> Optional[list]:
        try:
            data = await self._make_request("GET", "contacts", params={"query": query})
            if "_embedded" in data and "contacts" in data["_embedded"]:
                return data["_embedded"]["contacts"]
            return None
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 204:
                return None
            raise

    async def get_contact(self, contact_id: int) -> Optional[Dict[str, Any]]:
        try:
            return await self._make_request("GET", f"contacts/{contact_id}")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    async def update_contact(self, contact_id: int, new_data: Dict[str, Any]) -> None:
        raw_custom_fields = new_data.get("custom_fields_values")
        if not raw_custom_fields:
            return

        clean_custom_fields = []
        for field in raw_custom_fields:
            clean_field = {"values": field.get("values")}
            if field.get("field_id"):
                clean_field["field_id"] = field.get("field_id")
            elif field.get("field_code"):
                clean_field["field_code"] = field.get("field_code")
            clean_custom_fields.append(clean_field)

        payload = [{"id": contact_id, "custom_fields_values": clean_custom_fields}]
        await self._make_request("PATCH", "contacts", json=payload)

    async def transfer_notes(self, from_id: int, to_id: int) -> None:
        try:
            notes_data = await self._make_request("GET", f"contacts/{from_id}/notes")
            if not notes_data or "_embedded" not in notes_data:
                return
            notes = notes_data["_embedded"]["notes"]
            payload = [{"note_type": n["note_type"], "params": n["params"]} for n in notes]
            if payload:
                await self._make_request("POST", f"contacts/{to_id}/notes", json=payload)
        except httpx.HTTPStatusError:
            pass

    async def transfer_deals(self, from_id: int, to_id: int) -> None:
        try:
            contact_data = await self._make_request("GET", f"contacts/{from_id}?with=leads")
            if not contact_data or "_embedded" not in contact_data or "leads" not in contact_data["_embedded"]:
                return
            leads = contact_data["_embedded"]["leads"]
            payload = [{"to_entity_id": l["id"], "to_entity_type": "leads"} for l in leads]
            if payload:
                await self._make_request("POST", f"contacts/{to_id}/link", json=payload)
        except httpx.HTTPStatusError:
            pass

    async def delete_contact(self, contact_id: int) -> None:
        payload = [{"id": contact_id, "name": "ДУБЛЬ (Склеен)"}]
        try:
            await self._make_request("PATCH", "contacts", json=payload)
            logger.info(f"Контакт {contact_id} помечен как ДУБЛЬ (API не поддерживает полное удаление).")
        except httpx.HTTPStatusError as e:
            logger.warning(f"Не удалось переименовать дубль {contact_id}: {e.response.text}")