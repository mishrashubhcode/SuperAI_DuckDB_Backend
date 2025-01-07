from flask import Flask, request, jsonify , render_template , Response
from flask_cors import CORS
import duckdb
import pandas as pd
import os
import google.generativeai as genai
from dotenv import load_dotenv
import cloudinary
import cloudinary.uploader
from cloudinary.utils import cloudinary_url

# Load environment variables
load_dotenv()

google_api_key = os.getenv("GOOGLE_API_KEY")
cloudinary_cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME")
cloudinary_api_key = os.getenv("CLOUDINARY_API_KEY")
cloudinary_api_secret = os.getenv("CLOUDINARY_API_SECRET")
cloudinary.config( 
    cloud_name = cloudinary_cloud_name, 
    api_key = cloudinary_api_key, 
    api_secret = cloudinary_api_secret,
    secure=True
)

app = Flask(__name__)
cors = CORS(app,origins="*")

@app.route('/', methods=['GET'])
def home():
    return jsonify({"message":"Server running successfully"})

# Route for uploading files
@app.route('/upload_file', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "File Not Found."}), 400

    csv_file = request.files['file']
    if csv_file.filename == '':
        return jsonify({"error": "No File selected."}), 400

    try:
        
        upload_result = cloudinary.uploader.upload(
            csv_file,
            resource_type="raw",
            public_id=csv_file.filename.split('.')[0]
        )
        return jsonify({"message": "File uploaded successfully!", "filePath": upload_result["secure_url"]}), 200
    except Exception as e:
        return jsonify({"error": f"Error uploading the file: {str(e)}"}), 500

# Route for generating SQL
@app.route('/generate_sql', methods=['POST'])
def generate_sql():
    
    genai.configure(api_key=google_api_key)
    model = genai.GenerativeModel("gemini-2.0-flash-exp")
    data = request.get_json()
    if not data or 'text' not in data:
        return jsonify({"error": "Missing text input."}), 400

    text_input = data['text']

    if not data or 'filePath' not in data:
        return jsonify({"error": "No file uploaded. Please upload a file first."}), 400
    
    filePath = data['filePath']

    try:
        df = pd.read_csv(filePath)
    except Exception as e:
        return jsonify({"error": f"Error reading CSV file: {str(e)}"}), 400

    prompt = (
        f"You are an expert SQL generator. Given the following text request: \"{text_input}\" "
        f"and the structure of this CSV file: {df.head().to_string(index=False)}, "
        f"give answer in SQL query only irrespective of actual meaning and use table name as uploaded_csv and use proper alias where needed"
        f"take column headings as they are without adding any character to it or deleting white spaces"
        f"It should contain only SQL nothing else"
    )

    try:
        response = model.generate_content(prompt)
        sql_query = response.text
        print(f"Generated SQL query: {sql_query}")
    except Exception as e:
        return jsonify({"error": f"Error generating SQL: {str(e)}"}), 500

    sql_query = sql_query.replace("```", "").replace("sql", "").replace("\n", " ").strip()
    sql_query = sql_query.replace("your_table_name", "uploaded_csv")

    # Execute the SQL query using DuckDB
    try:
        conn = duckdb.connect()
        conn.register('uploaded_csv', df)
        output_table = conn.execute(sql_query).fetchdf()
    except Exception as e:
        return jsonify({"error": f"Error executing SQL: {str(e)}"}), 500

    csv_data = output_table.to_csv(index=False)

    return Response(
        csv_data,
        mimetype='text/csv',
        headers={"Content-Disposition": "attachment; filename=output.csv"}
    )

if __name__ == '__main__':
    # app.run(debug=True,port=5000)
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)