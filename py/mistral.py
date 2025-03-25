from uuid import uuid4

from r2r import R2RClient

client = R2RClient("http://localhost:8272")

client.documents.create(
    file_path="/Users/nolantremelling/Downloads/LDO TLE OP Division Order Title Opinion-1202509-DIGITAL-1862-003D-1950097758-DOUGLAS 01 01H-6_11_2012-1862-CGP 71 (1862)-2_28_2016 (1).PDF",
    id=uuid4(),
    ingestion_mode="ocr",
)


# import os

# from mistralai import Mistral

# api_key = os.environ["MISTRAL_API_KEY"]

# client = Mistral(api_key=api_key)

# # uploaded_pdf = client.files.upload(
# #     file={
# #         "file_name": '/Users/nolantremelling/Downloads/old_handwritten.pdf',
# #         "content": open('/Users/nolantremelling/Downloads/old_handwritten.pdf', "rb"),
# #     },
# #     purpose="ocr"
# # )

# response = client.files.retrieve(
#     file_id="bbf8e22e-8ebd-4fee-90bf-d6adf555a01e"
# )


# signed_url = client.files.get_signed_url(
#     file_id="bbf8e22e-8ebd-4fee-90bf-d6adf555a01e"
# )


# ocr_response = client.ocr.process(
#     model="mistral-ocr-latest",
#     document={
#         "type": "document_url",
#         "document_url": signed_url.url,
#     },
# )

# for page in ocr_response.pages:
#     print(page.markdown)
