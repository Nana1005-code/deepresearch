from io import BytesIO
from pathlib import Path
from docx import Document
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject

folder = Path(__file__).parent
doc = Document()
doc.add_heading('Original Word preview test', 0)
doc.add_paragraph('The original document must keep its formatting and bytes.')
doc.save(folder / 'original-check.docx')
writer = PdfWriter()
page = writer.add_blank_page(width=600, height=800)
font = DictionaryObject({NameObject('/Type'): NameObject('/Font'), NameObject('/Subtype'): NameObject('/Type1'), NameObject('/BaseFont'): NameObject('/Helvetica')})
page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'): writer._add_object(font)})})
stream = DecodedStreamObject()
stream.set_data(b'BT /F1 22 Tf 50 750 Td (Original PDF with original page layout.) Tj ET')
page[NameObject('/Contents')] = writer._add_object(stream)
writer.write(folder / 'original-check.pdf')
