import uvicorn
from fastapi.openapi.utils import get_openapi
from r2r.main import E2EPipelineFactory, R2RConfig
import os
import json

app = E2EPipelineFactory.create_pipeline(config=R2RConfig.load_config())

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    try:
        openapi_schema = get_openapi(
            title="Your API Title",
            version="1.0.0",
            description="Your API description",
            routes=app.routes,
        )
        app.openapi_schema = openapi_schema
        
        print("OpenAPI schema generated:")
        print(openapi_schema)
        
        # Save the OpenAPI schema to a file
        file_path = "swagger.json"
        with open(file_path, "w") as file:
            json.dump(openapi_schema, file)
        
        print(f"OpenAPI schema saved to: {file_path}")
        print(f"Current working directory: {os.getcwd()}")
        
        return app.openapi_schema
    
    except Exception as e:
        print(f"Error generating or saving OpenAPI schema: {str(e)}")
        return None

app.openapi = custom_openapi

custom_openapi()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
    
# import uvicorn
# from fastapi.openapi.utils import get_openapi

# from r2r.main import E2EPipelineFactory, R2RConfig

# # Creates a pipeline with default configuration
# # This is the main entry point for the application
# # The pipeline is built using the `config.json` file
# # Read more about the configuration in the documentation [https://r2r-docs.sciphi.ai/core-features/factory]
# app = E2EPipelineFactory.create_pipeline(config=R2RConfig.load_config())


# def custom_openapi():
#     if app.openapi_schema:
#         return app.openapi_schema
#     openapi_schema = get_openapi(
#         title="Your API Title",
#         version="1.0.0",
#         description="Your API description",
#         routes=app.routes,
#     )
#     app.openapi_schema = openapi_schema
#     import json

#     # Save the OpenAPI schema to a file
#     with open("swagger.json", "w") as file:
#         json.dump(openapi_schema, file)

#     return app.openapi_schema

# app.openapi = custom_openapi

# if __name__ == "__main__":
#     # Run the FastAPI application using Uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8000)
