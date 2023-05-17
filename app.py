import shutup
from paddleocr import PaddleOCR, draw_ocr
import warnings
import io
import threading
from PIL import Image
from flask import Flask, request, jsonify
import fitz
import cv2
import numpy as np
import requests
import sys
import multiprocessing

shutup.please()
app = Flask(__name__)

backend_url = 'http://13.50.249.27:8080/'
report_url = backend_url + 'api/report'

timeout = 5
try:
    response = requests.get(backend_url, timeout=timeout)
    response.raise_for_status()
    print('Backend Server is accepting requests')
except requests.exceptions.RequestException as e:
    print(f'Backend Server is not accepting requests: {e}')
    sys.exit()


@app.route('/scanPdf', methods=['POST'])
def upload_pdf():
    pdf_file = request.files.get('pdf')
    documentId = request.form.get('documentId')
    print('Document Recieved:', documentId)
    if not pdf_file:
        return jsonify({'error': 'No PDF file uploaded'})
    
    pdf_path = 'input.pdf'
    pdf_file.save(pdf_path)
    thread = multiprocessing.Process(target=scan_pdf, args=((pdf_path, documentId)))
    thread.start()
    return jsonify({'success': True, 'message': 'PDF file received successfully'})


medical_terms = ["haemoglobin", "rbc count", "m.c.v.", "m.c.h.", "m.c.h.c.", "mpv", "pct", "pdw",
                 "red cell distribution width (row)", "total leukocyte count", "metamyelocyte",
                 "differential leucocyte count", "packed cell volume", "total erythrocyte count",
                 "segmented neutrophils", "lymphocytes", "monocytes", "eosinophils", "basophils", "neutrophils", "lymphocytes", "monocytes", "platelet", "platelet count", "cholesterol total", "triglycerides", "hdl cholesterol", "ldl cholesterol", "vldl cholesterol", "non-hdl cholesterol", "hba1c-glycosylated hemoglobin", "promyelocyte", "myelocyte",
                 "glucose fasting", "glucose (pp)", "platelet", "ast-:alt ratio", "ggtp", "alkaline phosphatase (alp)", "crp (c-reactive protein)", "hba1c", "estimated average glucose (eag)", "glucose, fasting (f), plasma", "glucose, post prandial (pp), 2 hours,"]


def scan_pdf(pdf_path, documentId):
    print("Start OCR on document " + documentId)
    try:
        # Create an instance of the OCR model
        ocr_model = PaddleOCR(use_angle_cls=True, det_db_score_mode='slow')
        pdf_file = open(pdf_path, 'rb')
        # Extract images from the PDF and perform OCR on each image
        user_dict = {}
        with io.BytesIO(pdf_file.read()) as pdf_stream:
            pdf_doc = fitz.open(stream=pdf_stream, filetype="pdf")
            for page_num in range(pdf_doc.page_count):
                page = pdf_doc.load_page(page_num)
                mat = fitz.Matrix(2, 2)
                pm = page.get_pixmap(matrix=mat, alpha=False)
                if pm.width > 2000 or pm.height > 2000:
                    pm = page.get_pixmap(matrix=fitz.Matrix(1, 1), alpha=False)
                img = Image.frombytes("RGB", [pm.width, pm.height], pm.samples)
                img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
                result = ocr_model.ocr(img, cls=True)
                for idx in range(len(result)):
                    res = result[idx]
                    txts = [line[1][0] for line in res]
                    for x in range(len(txts)):
                        if txts[x].lower() in medical_terms:
                            val = txts[x+1]
                            user_dict[txts[x].upper()] = val
        print("Document: ", documentId, " Details: ", user_dict)
        data = {"documentId": documentId,
                "ocrStatus": "complete", "details": user_dict}
        print("data:", data)
        response = requests.post(report_url, json=data, verify=False)
        print("OCR: SUCCESS")
    except:
        print("Failed to perform OCR on document:", documentId)
        data = {"documentId": documentId,
                "ocrStatus": "failed", "details": {}}
        response = requests.post(report_url, json=data, verify=False)
        print("OCR: FAILED")
    print("OCR request sent to server, response:", response.json())


@app.route('/')
def hello():
    return "Hello Back4apper!"

if __name__ == '__main__':
    app.run(host='localhost', port=3000)
