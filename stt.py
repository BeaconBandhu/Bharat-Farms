from flask import Flask, request, render_template_string
import os
import dwani

# Initialize Flask app
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = './uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Set up Dwani API
dwani.api_key = "aranyabandhu2004@gmail.com _dwani_vishnuvardhana"
dwani.api_base = "https://dwani-amoghavarsha.hf.space"

# HTML Template
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Hindi Audio Transcription</title>
</head>
<body>
    <h2>Upload WAV File for Hindi Transcription</h2>
    <form method="POST" enctype="multipart/form-data">
        <input type="file" name="audio" accept=".wav" required>
        <input type="submit" value="Transcribe">
    </form>

    {% if result %}
        <h3>Transcription Result:</h3>
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
        file = request.files.get('audio')
        if file and file.filename.endswith('.wav'):
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'uploaded.wav')
            file.save(file_path)

            try:
                result = dwani.ASR.transcribe(
                    file_path=file_path,
                    language="hindi"
                )
            except Exception as e:
                error = f"Error during transcription: {str(e)}"
        else:
            error = "Please upload a valid .wav file."

    return render_template_string(HTML_TEMPLATE, result=result, error=error)

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5003, debug=True)