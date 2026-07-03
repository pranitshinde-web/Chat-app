from pydantic import BaseModel


class UploadResponse(BaseModel):
    file_url: str
    filename: str
    original_filename: str
    content_type: str
    size_bytes: int
