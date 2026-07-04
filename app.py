from flask import Flask, request, jsonify
from flask_cors import CORS
import cv2
import numpy as np
import datetime
import difflib
import re
import os
import json
import base64
from zhipuai import ZhipuAI
from dateutil.relativedelta import relativedelta
from calendar import monthrange
import gspread
from google.oauth2.service_account import Credentials

app = Flask(__name__)
CORS(app)

# ==============================================================================
# Constants & Corrections
# ==============================================================================
ALLOWED_CHARS = "BCEFGHJKLMNPRVXZ0123456789()"
GENERAL_CORRECTIONS = {
    "（": "(", "）": ")",
    " ": "", "D": "0", "O": "0", "I": "1", "l": "1"
}
KEYWORD_CORRECTIONS = {
    "GN12": "CN12", "@N12": "CN12", "CN1Z": "CN12", "CNIZ": "CN12", "GPEXP": "CPEXP", "G2EXP": "CPEXP",
    "5EXP": "CPEXP", "EPEX": "CPEXP", "FPEXP": "CPEXP", "CEXP": "CPEXP", "GCP": "CP", "SP": "CP",
    "()": "(L)", "(0)": "(L)", "(1)": "(L)", "(2)": "(L)", "(3)": "(L)", "(4)": "(L)", "(5)": "(L)",
    "(6)": "(L)", "(7)": "(L)", "(8)": "(L)", "(9)": "(L)", "(G)": "(L)", "(I)": "(L)", "(1": "(L)", "1)": "(L)"
}

lines = {"N12": "F", "N13": "G", "N14": "H", "N15": "J", "N16": "K", "N17": "L", "N18": "M", "N19": "N", "N21": "R",
         "N22": "V", "N23": "X", "N25": "Z", "N26": "B", "N30": "P"}
validity_months = {"3年": 36, "2.5年": 30, "2年": 24, "1.5年": 18, "1年": 12, "35个月": 35, "30个月": 30, "29个月": 29,
                   "23个月": 23, "18个月": 18, "17个月": 17, "11个月": 11}
in_advance_days_dict = {"当天": 0, "提前1天": 1, "提前2天": 2, "提前3天": 3, "提前4天": 4, "提前5天": 5}
shifts_dict = {"夜班": "1", "早班": "2", "中班": "3"}

# Initialize ZhipuAI
# The SDK automatically uses the ZHIPUAI_API_KEY environment variable.

SPREADSHEET_ID = '1L4rVsLqZuCjdzyfPt7BzE5Ei-LtKlN_m5y2NbnhoeJc'
SHEET_NAME = 'Sheet1'
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

def setup_google_sheets():
    try:
        # Check for raw JSON string in environment variable
        creds_json_str = os.environ.get("GOOGLE_CREDENTIALS_JSON")
        
        if creds_json_str:
            # Parse the JSON string directly
            creds_dict = json.loads(creds_json_str)
            creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
            client = gspread.authorize(creds)
        else:
            # Fallback: Check if the local file exists (for local testing or private repos)
            local_file = 'liquid-crossing-318502-21504d159a43.json'
            if os.path.exists(local_file):
                print("Using local credentials file.")
                client = gspread.service_account(filename=local_file)
            else:
                print("No credentials found. Please set GOOGLE_CREDENTIALS_JSON env var or provide the local file.")
                return None
                
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        worksheet = spreadsheet.worksheet(SHEET_NAME)
        return worksheet
    except Exception as e:
        print(f"Error setting up Google Sheets: {e}")
        return None

worksheet = setup_google_sheets()

def perform_ocr_on_image(image_bytes):
    try:
        client = ZhipuAI() # uses ZHIPUAI_API_KEY env var
        
        # Encode image to base64
        img_base64 = base64.b64encode(image_bytes).decode('utf-8')
        
        # Call Zhipu AI Vision Model
        response = client.chat.completions.create(
            model="glm-4v",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Please extract the text, production date code, and serial numbers from this image. Only return the exact text you see, without any conversational explanations."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{img_base64}"
                            }
                        }
                    ]
                }
            ]
        )
        
        if not response.choices or not response.choices[0].message.content:
            return ""
            
        raw_text = response.choices[0].message.content
        processed_text = raw_text.upper()
        for key, value in GENERAL_CORRECTIONS.items():
            processed_text = processed_text.replace(key, value)
        processed_text = re.sub(f'[^{ALLOWED_CHARS}]', '', processed_text)
        sorted_keywords = sorted(KEYWORD_CORRECTIONS.items(), key=lambda item: len(item[0]), reverse=True)
        for key, value in sorted_keywords:
            processed_text = processed_text.replace(key, value)
        return processed_text
    except Exception as e:
        print(f"OCR Error: {e}")
        return ""

def calculate_correct_answer(line_selected, front_back_selected, serial_selected, validity_selected, days_advance, shift_cn):
    line = lines.get(line_selected, "")
    validity_month = validity_months.get(validity_selected, 0)
    days_advance_digit = in_advance_days_dict.get(days_advance, 0)
    shift_number = shifts_dict.get(shift_cn, "1")

    now = datetime.datetime.now()
    production_date = now + datetime.timedelta(days=days_advance_digit)
    day_of_year = production_date.timetuple().tm_yday
    front_date1 = str(production_date.year)[-1] + f"{day_of_year:03d}"
    front_date2 = production_date.strftime("%d%m%y")
    front_date3 = production_date.strftime("%Y%m%d")

    end_date_calculated = production_date + relativedelta(months=validity_month)
    last_day_of_month = monthrange(end_date_calculated.year, end_date_calculated.month)[1]
    end_date = end_date_calculated.replace(day=last_day_of_month) if end_date_calculated.day > last_day_of_month else end_date_calculated
    end_date1 = end_date.strftime("%Y%m%d")
    end_date2 = end_date.strftime("%m%y")
    end_date4 = end_date.strftime(" %m %y")

    front1 = f"(L){front_date1}CN12{line}{serial_selected}"
    front2 = f"(L){front_date1}CN12{shift_number}{line}"
    front3 = f"(L){front_date2}C{line}{serial_selected}"
    front4 = f"(L){front_date2}C{shift_number}{line}"
    front5 = f"{front_date3}C{line}{serial_selected}"
    back1 = f"CPEXP{end_date1}"
    back2 = f"CPEXP{end_date2}"
    back3 = "CP"
    back4 = f"CP{end_date4}"
    back5 = f"CP{front_date2}"
    back6 = f"EXP{end_date1}"
    back7 = f"EXP{end_date2}(L){front_date1}CN12{shift_number}{line}"
    back8 = f"CPEXP{end_date2}(L){front_date1}CN12{line}{serial_selected}"
    back9 = f"CPEXP{end_date1}(L){front_date1}CN12{line}{serial_selected}"

    front_back_text = {
        "(L)YJJJCN12LN": front1, "(L)YJJJCN12SL": front2, "(L)DDMMYYCLN": front3,
        "(L)DDMMYYCSL": front4, "YYYYMMDDCLN": front5, "CPEXPYYYYMMDD": back1,
        "CPEXPMMYY": back2, "CP": back3, "CP MM YY": back4,
        "CPDDMMYY(当前日期)": back5, "EXPYYYYMMDD": back6,
        "EXPMMYY(L)YJJJCN12SL": back7, "CPEXPMMYY(L)YJJJCN12LN": back8, "CPEXPYYYYMMDD(L)YJJJCN12LN": back9
    }
    return front_back_text.get(front_back_selected, "计算错误")

def evaluate_ai_levels(correct_answer_text, ocr_result_text):
    answer_digital = "".join(re.findall(r'\d+', correct_answer_text))
    answer_character = "".join(re.findall(r'[^0-9]', correct_answer_text))
    result_digital = "".join(re.findall(r'\d+', ocr_result_text))
    result_character = "".join(re.findall(r'[^0-9]', ocr_result_text))
    
    levels = {"4": "", "3": "", "2": "", "1": ""}
    digital_match = answer_digital in result_digital if answer_digital and result_digital else False
    
    if digital_match:
        if answer_character and result_character and answer_character in result_character:
            levels["4"] = '数字和字母都连续齐全'
        if len(answer_character) >= 3 and len(result_character) >= 3 and answer_character[-3:] == result_character[-3:]:
            levels["3"] = '数字连续齐全、包含最后3个字母'
        if len(answer_character) >= 2 and len(result_character) >= 2 and answer_character[-2:] == result_character[-2:]:
            levels["2"] = '数字连续齐全、包含最后2个字母'
        if len(answer_character) >= 1 and len(result_character) >= 1 and answer_character[-1:] == result_character[-1:]:
            levels["1"] = '数字连续齐全、包含最后1个字母'
            
    return levels

def append_to_sheets(data):
    if worksheet is None:
        print("Google Sheets not initialized.")
        return False
    try:
        worksheet.append_row(data, value_input_option='USER_ENTERED')
        return True
    except Exception as e:
        print(f"Error appending to Google Sheets: {e}")
        return False

@app.route('/api/ocr', methods=['POST'])
def process_ocr():
    try:
        line = request.form.get('line', 'N12')
        front_back = request.form.get('front_back', '(L)YJJJCN12LN')
        serial = request.form.get('serial', '1')
        validity = request.form.get('validity', '3年')
        advance = request.form.get('advance', '当天')
        shift = request.form.get('shift', '早班')
        
        file = request.files.get('image')
        if not file:
            return jsonify({'error': 'No image provided'}), 400
            
        in_memory_file = file.read()
        
        # We still decode with cv2 to validate it's an image, but pass the raw bytes to Zhipu
        nparr = np.frombuffer(in_memory_file, np.uint8)
        img_np = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if img_np is None:
            return jsonify({'error': 'Invalid image format'}), 400

        ocr_result_text = perform_ocr_on_image(in_memory_file)
        correct_answer_text = calculate_correct_answer(line, front_back, serial, validity, advance, shift)
        
        rate = 0.0
        if ocr_result_text and correct_answer_text:
            rate = difflib.SequenceMatcher(None, ocr_result_text, correct_answer_text).ratio() * 100
        similarity_rate_text = f"{rate:.2f}%"
        
        ai_levels = evaluate_ai_levels(correct_answer_text, ocr_result_text)
        
        if ocr_result_text:
            data_to_send = [
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                line, front_back, serial, validity, advance, shift,
                ocr_result_text, correct_answer_text, similarity_rate_text,
                ai_levels.get("4", ""), ai_levels.get("3", ""), 
                ai_levels.get("2", ""), ai_levels.get("1", "")
            ]
            sheets_success = append_to_sheets(data_to_send)
        else:
            sheets_success = False
            
        return jsonify({
            'ocr_result': ocr_result_text,
            'correct_answer': correct_answer_text,
            'similarity_rate': similarity_rate_text,
            'ai_levels': ai_levels,
            'sheets_saved': sheets_success
        })
        
    except Exception as e:
        print(f"Server Error: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
