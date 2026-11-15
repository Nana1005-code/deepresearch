import json
import sys
import tempfile
import unittest
from unittest.mock import patch
from io import BytesIO
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from document_api import router
from services.document_library import DocumentLibrary
from storage import Store


class DocumentPreviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = Store(Path(self.tmp.name) / "test.sqlite3")
        self.library = DocumentLibrary(self.store)
        app = FastAPI()
        app.include_router(router(self.library))
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def upload(self, name, content):
        response = self.client.post("/documents", files={"file": (name, content)})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()["id"]

    def preview(self, identifier):
        return self.client.get(f"/documents/{identifier}/text")

    def test_original_returns_identical_bytes_without_extraction(self):
        for name, content, charset in [
            ("原文件.md", '# 标题\n<script>alert(1)</script>\n这是一份原始文献。'.encode(), "utf-8"),
            ("中文原文件.txt", '中文原文件需要保留所有字节，不能在预览时转换文本。'.encode("gb18030"), "gb18030"),
        ]:
            with self.subTest(name=name):
                identifier = self.upload(name, content)
                with patch.object(self.library, "_extract", side_effect=AssertionError("preview must not extract")):
                    response = self.client.get(f"/documents/{identifier}/original")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.content, content)
                self.assertTrue(response.headers["content-disposition"].startswith("inline;"))
                self.assertEqual(response.headers["content-type"], f"text/plain; charset={charset}")
                self.assertEqual(response.headers["x-content-type-options"], "nosniff")
                download = self.client.get(f"/documents/{identifier}/download")
                self.assertTrue(download.headers["content-disposition"].startswith("attachment;"))
                self.assertEqual(download.content, content)

    def test_full_text_preserves_line_breaks_without_chunk_overlap(self):
        text = "标题\n\n" + "\n".join(f"第 {i} 行的研究正文。" for i in range(900))
        identifier = self.upload("完整正文.txt", text.encode())
        response = self.preview(identifier)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["cache-control"], "no-store")
        data = response.json()
        self.assertGreater(data["document"]["chunk_count"], 1)
        self.assertEqual(data["text"], text)
        self.assertNotIn("stored_path", data["document"])
        self.assertNotIn("sha256", data["document"])

    def test_markdown_and_gbk_text_are_not_html(self):
        for name, text, encoding in [
            ("说明.md", '# 原始 Markdown\n<script>alert("test")</script>\n**保留文本**', "utf-8"),
            ("中文.txt", "这是用于验证中文编码的本地文献。\n解析后的内容应完整保留。", "gb18030"),
        ]:
            with self.subTest(name=name):
                response = self.preview(self.upload(name, text.encode(encoding)))
                self.assertEqual(response.json()["text"], text)
                self.assertTrue(response.headers["content-type"].startswith("application/json"))

    def test_docx_and_pdf(self):
        from docx import Document
        from pypdf import PdfWriter
        from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject

        doc = Document()
        doc.add_paragraph("Word 文献正文，测试完整文本阅读功能。")
        doc.add_table(rows=1, cols=1).cell(0, 0).text = "表格中的研究结论"
        word = BytesIO()
        doc.save(word)
        word_id = self.upload("论文.docx", word.getvalue())
        original = self.client.get(f"/documents/{word_id}/original")
        self.assertEqual(original.content, word.getvalue())
        self.assertTrue(original.headers["content-disposition"].startswith("attachment;"))
        response = self.preview(word_id)
        self.assertIn("Word 文献正文", response.json()["text"])
        self.assertIn("表格中的研究结论", response.json()["text"])

        writer = PdfWriter()
        font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"), NameObject("/BaseFont"): NameObject("/Helvetica")})
        for number in [1, 2]:
            page = writer.add_blank_page(width=600, height=800)
            page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})})
            stream = DecodedStreamObject()
            stream.set_data(f"BT /F1 12 Tf 50 750 Td (Preview page {number} contains research evidence.) Tj ET".encode())
            page[NameObject("/Contents")] = writer._add_object(stream)
        pdf = BytesIO()
        writer.write(pdf)
        pdf_id = self.upload("paper.pdf", pdf.getvalue())
        with patch.object(self.library, "_extract", side_effect=AssertionError("preview must not extract")):
            original = self.client.get(f"/documents/{pdf_id}/original")
        self.assertEqual(original.content, pdf.getvalue())
        self.assertEqual(original.headers["content-type"], "application/pdf")
        self.assertTrue(original.headers["content-disposition"].startswith("inline;"))
        response = self.preview(pdf_id)
        self.assertEqual(response.json()["document"]["page_count"], 2)
        self.assertIn("Preview page 1", response.json()["text"])
        self.assertIn("\n\nPreview page 2", response.json()["text"])

    def test_missing_deleted_and_missing_original(self):
        self.assertEqual(self.preview("missing").status_code, 404)
        self.assertEqual(self.client.get("/documents/missing/original").status_code, 404)
        identifier = self.upload("删除测试.txt", b"This is a document for testing deleted previews.")
        self.client.delete(f"/documents/{identifier}")
        self.assertEqual(self.preview(identifier).status_code, 404)
        self.assertEqual(self.client.get(f"/documents/{identifier}/original").status_code, 404)
        identifier = self.upload("遗失测试.txt", b"This is a document for testing a missing original.")
        Path(self.library.get_document(identifier)["stored_path"]).unlink()
        self.assertEqual(self.preview(identifier).status_code, 404)

    def test_outside_library_path_is_not_read(self):
        identifier = self.upload("路径测试.txt", b"This is a document for testing path containment.")
        outside = Path(self.tmp.name) / "private.txt"
        outside.write_text("must not return this text", encoding="utf-8")
        record = self.library.get_document(identifier)
        record["stored_path"] = str(outside)
        with self.store.connect() as db:
            db.execute("UPDATE documents SET data=? WHERE id=?", (json.dumps(record), identifier))
        response = self.preview(identifier)
        self.assertEqual(response.status_code, 404)
        self.assertNotIn("must not return", response.text)
        self.assertEqual(self.client.get(f"/documents/{identifier}/original").status_code, 404)


if __name__ == "__main__":
    unittest.main()
