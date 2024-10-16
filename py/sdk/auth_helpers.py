# sdk/auth_helpers.py

from typing import Any, Dict

def process_login_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
    self.access_token = response["results"]["access_token"]["token"]
    self._refresh_token = response["results"]["refresh_token"]["token"]
    return response
