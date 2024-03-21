
from itertools import product
import os
from typing import Optional


class IonicClient:
    def __init__(self, api_base: str = "api.ioniccommerce.com", api_key: str = os.getenv("IONIC_API_KEY")) -> None:
        if not api_key:
            raise ValueError(
                "Please set the `IONIC_API_KEY` env var or pass a parameter to use `IonicCLient`."
            )
        
        # temp local import for dependency mgmt
        from ionic import Ionic as IonicSDK
        
        
        self.client = IonicSDK(api_key_header=api_key)

    def query(
        self,
        query: str,
        num_results: Optional[int] = 5,
        min_price: Optional[int] = None,
        max_price: Optional[int] = None,
    ) -> list[product]:
        # temp local import for dependency mgmt
        from ionic.models.components import Product, QueryAPIRequest
        from ionic.models.components import Query as SDKQuery
        from ionic.models.operations import QueryResponse, QuerySecurity

        request = QueryAPIRequest(
            query=SDKQuery(
                query=query,
                num_results=num_results
            )
        )
        response: QueryResponse = self.client.query(
            request=request,
            security=QuerySecurity(),
        )

        return [
            product
            for result in response.query_api_response.results
            for product in result.products
        ]