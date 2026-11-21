import os
import tempfile
from flask import Flask, request, Response
from pypdf import PdfReader

try:
    import pymupdf
except ImportError:
    import fitz as pymupdf

from rapidocr_onnxruntime import RapidOCR

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024

engine = RapidOCR()


def ocr_page(doc, page_index):
    png = doc[page_index].get_pixmap(dpi=200).tobytes("png")
    result, _ = engine(png)

    if not result:
        return ""

    items = []
    for box, text, score in result:
        ys = [p[1] for p in box]
        xs = [p[0] for p in box]
        items.append((min(ys), max(ys), min(xs), text))

    items.sort(key=lambda x: (x[0], x[2]))

    lines = []
    current = []
    last_mid = None
    last_h = None

    for top, bottom, left, text in items:
        mid = (top + bottom) / 2
        height = bottom - top

        if (
            last_mid is not None
            and abs(mid - last_mid) > max(last_h, height) * 0.6
        ):
            lines.append(current)
            current = []

        current.append((left, text))
        last_mid = mid
        last_h = height

    if current:
        lines.append(current)

    return "\n".join(
        " ".join(text for _, text in sorted(line))
        for line in lines
    )


@app.route("/invoice", methods=["POST"])
def invoice():
    if "file" not in request.files:
        return Response("Please upload PDF using the 'file' field.", status=400)

    uploaded_file = request.files["file"]

    if not uploaded_file.filename:
        return Response("Please select a PDF file.", status=400)

    if not uploaded_file.filename.lower().endswith(".pdf"):
        return Response("Only PDF files are allowed.", status=400)

    temp_path = None
    doc = None

    try:
        with tempfile.NamedTemporaryFile(
            suffix=".pdf", delete=False
        ) as temp:
            uploaded_file.save(temp)
            temp_path = temp.name

        reader = PdfReader(temp_path, strict=False)

        if reader.is_encrypted:
            return Response("Encrypted PDF is not supported.", status=400)

        doc = pymupdf.open(temp_path)
        extracted_pages = []

        for i, page in enumerate(reader.pages):
            text = (page.extract_text() or "").strip()

            if not text:
                text = ocr_page(doc, i).strip()

            if text:
                extracted_pages.append(text)

        # Return only extracted text
        return Response(
            "\n\n".join(extracted_pages),
            mimetype="text/plain; charset=utf-8"
        )

    except Exception:
        app.logger.exception("PDF extraction failed")
        return Response("PDF processing failed.", status=500)

    finally:
        if doc is not None:
            doc.close()

        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


@app.errorhandler(413)
def file_too_large(error):
    return Response("PDF exceeds the 50 MB limit.", status=413)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)