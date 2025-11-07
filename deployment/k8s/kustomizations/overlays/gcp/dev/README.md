# About
This overlay provides convenient defaults and is intended for quick setup and testing.  
It is **not** recommended for production use.

# Installation

## Configuration
1. Update `overlays/gcp/dev/include/sec-r2r-file.yaml`.
2. Set LLM keys for the models used in `sec-r2r-file.yaml` within `overlays/gcp/dev/include/sec-r2r.yaml`.
3. (Optional) Adjust non-default API endpoints in `overlays/gcp/dev/include/cm-r2r.yaml`.

## Execution
Apply the configuration with:
```shell
kustomize build --enable-helm . | kubectl apply -f -
```
