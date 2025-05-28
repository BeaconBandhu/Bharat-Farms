from flask import Flask, request, render_template_string
import os
import dwani

# Initialize Flask app
app = Flask(__name__)

# Setup Dwani API
dwani.api_key = "aranyabandhu2004@gmail.com _dwani_vishnuvardhana"
dwani.api_base = "https://dwani-vishnuvardhana.hf.space"

# HTML Template in a variable
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Crop Disease Diagnosis</title>
</head>
<body>
    <h2>Upload Crop Image</h2>
    <form method="POST" enctype="multipart/form-data">
        <input type="file" name="file" accept="image/*" required>
        <input type="submit" value="Diagnose">
    </form>

    {% if result %}
        <h3>Result (Translated in Hindi):</h3>
        <p>{{ result }}</p>
    {% elif error %}
        <p style="color:red;">{{ error }}</p>
    {% endif %}
</body>
</html>
"""

@app.route('/', methods=['GET', 'POST'])
def index():
    result = None
    error = None

    if request.method == 'POST':
        uploaded_file = request.files.get('file')

        if uploaded_file and uploaded_file.filename != '':
            file_path = os.path.join('.', 'crop.jpg')
            uploaded_file.save(file_path)

            try:
                result = dwani.Vision.caption(
                    file_path=file_path,
                    query="identify the disease in the plant",
                    src_lang="eng_Latn",
                    tgt_lang="hin_Deva"
                )
            except Exception as e:
                error = f"Error during API call: {str(e)}"
        else:
            error = "No file uploaded."

    return render_template_string(HTML_TEMPLATE, result=result, error=error)

if __name__ == '__main__':
    app.run(debug=True)
