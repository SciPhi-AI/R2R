import os

from r2r.codesearch.scip_pb2 import Index


class Indexer:
    def __init__(self, path: str = "index.scip", project_name: str = "r2r"):
        self.path = path
        self.project_name = project_name
        self.index = self._load_index_protobuf()

    def _load_index_protobuf(self) -> Index:
        """
        Loads and returns an Index protobuf object from the given file path.
        """
        index = Index()
        with open(self.path, "rb") as f:
            index.ParseFromString(f.read())
        return index

    def extractor(self):
        for document in self.index.documents:
            with open(
                os.path.join(self.project_name, document.relative_path), "r"
            ) as f:
                content = f.readlines()
            for i, occurence in enumerate(document.occurrences):
                if "python r2r" not in occurence.symbol:
                    continue
                if len(occurence.enclosing_range) != 4:
                    continue
                # bounding box coordinates
                symbol = "".join(occurence.symbol.split("`")[1:])
                line, col, end_line, end_col = occurence.enclosing_range
                extraction = "".join(content[line:end_line])
                yield symbol, extraction
