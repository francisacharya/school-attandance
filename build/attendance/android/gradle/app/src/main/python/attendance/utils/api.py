import httpx
import json


class ApiClient:
    def __init__(self, base_url=None):
        if base_url is None:
            import os, sys
            if hasattr(sys, 'getandroidapilevel') or "ANDROID_ROOT" in os.environ:
                base_url = "http://10.0.2.2:8080"
            else:
                base_url = "http://127.0.0.1:8080"
        self.base_url = base_url
        self.token = None
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=30.0)

    def _auth_headers(self):
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    async def set_token(self, token):
        self.token = token
        self._client.headers.update({"Authorization": f"Bearer {token}"})

    async def login(self, username, password):
        try:
            data = {"username": username, "password": password}
            response = await self._client.post("/token", data=data)
            response.raise_for_status()
            result = response.json()
            await self.set_token(result["access_token"])
            return result
        except Exception as e:
            raise Exception(f"Login failed: {str(e)}")

    async def get(self, endpoint, params=None):
        try:
            response = await self._client.get(endpoint, params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise Exception(f"GET {endpoint} failed: {str(e)}")

    async def post(self, endpoint, data=None):
        try:
            response = await self._client.post(endpoint, json=data)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise Exception(f"POST {endpoint} failed: {str(e)}")

    async def put(self, endpoint, data=None):
        try:
            response = await self._client.put(endpoint, json=data)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise Exception(f"PUT {endpoint} failed: {str(e)}")

    async def delete(self, endpoint):
        try:
            response = await self._client.delete(endpoint)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise Exception(f"DELETE {endpoint} failed: {str(e)}")

    async def close(self):
        await self._client.aclose()


# Global api client instance
api_client = ApiClient()
