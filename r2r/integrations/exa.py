import os
from typing import Optional


class ExaClient:
    def __init__(self, api_key: Optional[str] = None) -> None:
        try:
            from exa_py import Exa
        except ImportError:
            raise ImportError(
                "Please install the `exa-py` package to use `ExaClient`."
            )

        api_key = api_key or os.getenv("EXA_API_KEY")

        if not api_key:
            raise ValueError(
                "Please set the `EXA_API_KEY` environment variable to use `ExaClient`."
            )

        self.exa = Exa(api_key)

    def _search_and_contents(
        self,
        query: str,
        limit: int = 10,
        num_highlights: int = 2,
        num_sentences: int = 4,
        **kwargs
    ) -> list:
        return self.exa.search_and_contents(
            query,
            num_results=limit,
            highlights={
                "highlights_per_url": num_highlights,
                "num_sentences": num_sentences,
                "query": query,
            },
            use_autoprompt=True,
            **kwargs
        )

    def get_raw(self, query: str, limit: int = 10, **kwargs) -> list:
        search = self._search_and_contents(query, limit, **kwargs)

        # Transform to be consistent w/ Serper API
        xf_results = []
        for i, result in enumerate(search.results):
            xf_results.append(
                {
                    "title": result.title,
                    "link": result.url,
                    "snippet": ".".join(result.highlights),
                    "position": i + 1,
                    "type": "organic",
                }
            )
        return xf_results

    @staticmethod
    def construct_context(results: list) -> str:
        from .serper import SerperClient

        return SerperClient.construct_context(results)
