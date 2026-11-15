
"""本地文献管理 API。"""

from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse

from services.document_library import (
    MAX_UPLOAD_BYTES,
    DocumentLibrary,
    DuplicateDocumentError,
)


def router(library: DocumentLibrary):

    api = APIRouter(
        prefix="/documents",
        tags=["local-documents"]
    )

    # 获取文献列表
    @api.get("")
    def list_documents():
        return library.list_documents()

    # 上传文献
    @api.post("", status_code=201)
    async def upload_document(
        file: UploadFile = File(...)
    ):

        filename = file.filename or ""

        try:

            content = await file.read(
                MAX_UPLOAD_BYTES + 1
            )

            if len(content) > MAX_UPLOAD_BYTES:
                raise HTTPException(
                    413,
                    "单个文件不能超过 25 MB"
                )

            return library.add_bytes(
                filename,
                content
            )

        except DuplicateDocumentError as exc:

            raise HTTPException(
                409,
                {
                    "message": str(exc),
                    "document": library.public_record(
                        exc.document
                    ),
                },
            ) from exc

        except ValueError as exc:

            raise HTTPException(
                400,
                str(exc)
            ) from exc

        finally:
            await file.close()

    @api.get("/{identifier}/text")
    def document_text(identifier: str, response: Response):
        response.headers["Cache-Control"] = "no-store"
        try:
            return library.get_text(identifier)
        except (KeyError, FileNotFoundError) as exc:
            raise HTTPException(404, "本地文献或原始文件不存在，请重新导入") from exc
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        except OSError as exc:
            raise HTTPException(503, "暂时无法读取原始文献，请稍后重试") from exc

    @api.get("/{identifier}/original")
    def open_original(identifier: str):
        return original_response(identifier, inline=True)

    # 下载原始文献
    @api.get("/{identifier}/download")
    def download_document(identifier: str):
        return original_response(identifier, inline=False)

    def original_response(identifier: str, inline: bool):

        try:
            record = library.get_document(identifier)

        except KeyError as exc:
            raise HTTPException(
                404,
                str(exc)
            ) from exc

        path = Path(
            record.get("stored_path", "")
        )

        if (
            not path.is_file()
            or path.resolve().parent
            != library.storage_dir.resolve()
        ):
            raise HTTPException(
                404,
                "原始文献文件不存在"
            )

        extension = record.get("extension", "")
        media_type = record.get("mime_type", "application/octet-stream")
        can_preview = extension in {".pdf", ".txt", ".md", ".markdown"}
        if inline and extension in {".txt", ".md", ".markdown"}:
            # Only identify the encoding; return the unchanged original bytes.
            # Markdown/HTML-like text must never execute as an HTML document.
            encoding = "utf-8"
            try:
                path.read_bytes().decode("utf-8-sig")
            except UnicodeDecodeError:
                encoding = "gb18030"
            media_type = f"text/plain; charset={encoding}"

        return FileResponse(
            path,
            media_type=media_type,
            filename=record.get(
                "original_name",
                "document"
            ),
            content_disposition_type="inline" if inline and can_preview else "attachment",
            headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "no-store"},
        )

    # 删除文献
    @api.delete("/{identifier}", status_code=204)
    def delete_document(identifier: str):

        try:
            library.delete_document(identifier)

        except KeyError as exc:
            raise HTTPException(
                404,
                str(exc)
            ) from exc

        except ValueError as exc:
            raise HTTPException(
                409,
                str(exc)
            ) from exc

        return None

    return api
