from flask import Flask, request, render_template_string
import requests
import datetime
import random
import dwani

# Configure Dwani
dwani.api_key = "aranyabandhu2004@gmail.com _dwani_vishnuvardhana"
dwani.api_base = "https://dwani-vishnuvardhana.hf.space"

app = Flask(__name__)

WEATHER_API_KEY = "88fd7918ff4041a69aa224546252305"

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Weather & Crop Suggestion System</title>
</head>
<body>
    <h1>Weather Forecast & Crop Suggestion</h1>
    <form method="POST">
        <label>Enter City: </label>
        <input type="text" name="city" value="{{ city or '' }}" required>
        <br><br>
        <button name="action" value="today">Get Today's Weather</button>
        <button name="action" value="300day">300-Day Forecast & Crop Suggestion</button>
    </form>

    {% if error %}
    <p style="color:red;">{{ error }}</p>
    {% endif %}

    {% if today_weather %}
    <h2>Today's Weather for {{ city.title() }}</h2>
    <p>Temperature: {{ today_weather.temp }} °C</p>
    <p>Condition: {{ today_weather.condition }}</p>
    {% endif %}

    {% if forecast %}
    <h2>300-Day Simulated Forecast for {{ city.title() }}</h2>
    <div style="max-height: 300px; overflow-y: scroll; border: 1px solid #ccc; padding:10px;">
        <ul>
        {% for day in forecast %}
            <li>{{ day }}</li>
        {% endfor %}
        </ul>
    </div>
    {% endif %}

    {% if crop_suggestion %}
    <h2>Crop Recommendation (Hindi)</h2>
    <pre style="white-space: pre-wrap; border: 1px solid green; background: #e8f5e9; padding: 10px;">{{ crop_suggestion }}</pre>
    {% endif %}

    <hr>
    <h3>API Debug Info</h3>
    <pre>{{ raw_response }}</pre>
</body>
</html>
"""

def get_today_weather(city):
    try:
        url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={WEATHER_API_KEY}&units=metric"
        res = requests.get(url)
        data = res.json()
        if data.get("cod") != 200:
            return None, data.get("message", "Error fetching weather")
        temp = data["main"]["temp"]
        condition = data["weather"][0]["description"].capitalize()
        return {"temp": temp, "condition": condition}, ""
    except Exception as e:
        return None, str(e)

def generate_300_day_weather():
    today = datetime.date.today()
    weather_data = []
    for i in range(1, 301):
        date = today + datetime.timedelta(days=i)
        temp = round(random.uniform(18, 38), 1)
        condition = random.choice(["Sunny", "Rainy", "Cloudy", "Partly Cloudy", "Thunderstorm"])
        weather_data.append(f"{date}: {temp}°C, {condition}")
    return weather_data

@app.route("/", methods=["GET", "POST"])
def index():
    city = ""
    action = ""
    today_weather = None
    forecast = []
    crop_suggestion = ""
    error = ""
    raw_response = ""

    if request.method == "POST":
        city = request.form.get("city", "").strip()
        action = request.form.get("action", "")

        if not city:
            error = "Please enter a city name."
        else:
            if action == "today":
                today_weather, error = get_today_weather(city)
                if error:
                    today_weather = None

            elif action == "300day":
                forecast = generate_300_day_weather()
                weather_summary = "\n".join(forecast[:20])
                prompt_text = (
                    f"Here is the 300-day weather forecast data for my location:\n{weather_summary}\n\n"
                    "Based on this data, please recommend the best crop to be grown in the next season."
                )
                try:
                    response = dwani.Chat.create(
                        prompt=prompt_text,
                        src_lang="eng_Latn",
                        tgt_lang="hin_Deva"
                    )
                    raw_response = str(response)
                    for key in ["generated_text", "text", "output", "result", "answer", "message"]:
                        if isinstance(response, dict) and key in response:
                            val = response[key]
                            if val and isinstance(val, str) and val.strip():
                                crop_suggestion = val
                                break
                    if not crop_suggestion:
                        crop_suggestion = "No suggestion received from Dwani AI."
                except Exception as e:
                    error = f"Error calling Dwani API: {str(e)}"

    return render_template_string(
        HTML_TEMPLATE,
        city=city,
        today_weather=today_weather,
        forecast=forecast,
        crop_suggestion=crop_suggestion,
        error=error,
        raw_response=raw_response
    )

if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
