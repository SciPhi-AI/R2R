from r2r import R2RClient
from uuid import uuid4


client = R2RClient("http://localhost:8272")

client.documents.create(
    file_path='/Users/nolantremelling/Downloads/LDO TLE OP Division Order Title Opinion-1202509-DIGITAL-1862-003D-1950097758-DOUGLAS 01 01H-6_11_2012-1862-CGP 71 (1862)-2_28_2016 (1).PDF',
    id=uuid4(),
    ingestion_mode="mistral-ocr"
)



# from mistralai import Mistral, OCRPageObject
# import os

# api_key = os.environ["MISTRAL_API_KEY"]

# client = Mistral(api_key=api_key)

# uploaded_pdf = client.files.upload(
#     file={
#         "file_name": 'LDO TLE OP Division Order Title Opinion-1202509-DIGITAL-1862-003D-1950097758-DOUGLAS 01 01H-6_11_2012-1862-CGP 71 (1862)-2_28_2016 (1).PDF',
#         "content": open('/Users/nolantremelling/Downloads/LDO TLE OP Division Order Title Opinion-1202509-DIGITAL-1862-003D-1950097758-DOUGLAS 01 01H-6_11_2012-1862-CGP 71 (1862)-2_28_2016 (1).PDF', "rb"),
#     },
#     purpose="ocr"
# )  

# print(uploaded_pdf)

# response = client.files.retrieve(file_id='9b306630-89f2-4479-a64e-cca013a4b77d')

# print(response)

# signed_url = client.files.get_signed_url(file_id='9b306630-89f2-4479-a64e-cca013a4b77d')

# print(signed_url)

# ocr_response = client.ocr.process(
#     model="mistral-ocr-latest",
#     document={
#         "type": "document_url",
#         "document_url": signed_url.url,
#     }
# )

# print(len(ocr_response.pages))