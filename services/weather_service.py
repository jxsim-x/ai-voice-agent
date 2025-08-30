import logging
import requests
import re
from typing import Dict, Optional, Tuple
import json
from datetime import datetime

logger = logging.getLogger(__name__)

class WeatherService:
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("Visual Crossing Weather API key is required")
        
        self.api_key = api_key
        self.base_url = "https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline"
        logger.info("Weather Service initialized with Visual Crossing Weather API")
    
    def detect_weather_intent(self, text: str) -> bool:
        """Detect if user is asking about weather"""
        weather_keywords = [
            'weather', 'temperature', 'temp', 'hot', 'cold', 'rain', 'sunny', 
            'cloudy', 'wind', 'humidity', 'forecast', 'climate', 'degrees',
            'celsius', 'fahrenheit', 'snow', 'storm', 'clear', 'overcast',
            'raining', 'snowing', 'windy', 'humid', 'dry', 'wet'
        ]
        
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in weather_keywords)
    
    def extract_location(self, text: str) -> Optional[str]:
        """Extract location from user text"""
        text_lower = text.lower()
        
        # Common patterns for location
        location_patterns = [
            r'weather (?:in|at|for) ([a-zA-Z\s,]+)',
            r'temperature (?:in|at|for) ([a-zA-Z\s,]+)',  
            r'(?:how (?:is|hot|cold)) .* (?:in|at) ([a-zA-Z\s,]+)',
            r'(?:what\'s|whats) .* weather .* (?:in|at) ([a-zA-Z\s,]+)',
            r'rain(?:ing)? (?:in|at) ([a-zA-Z\s,]+)',
            r'sunny (?:in|at) ([a-zA-Z\s,]+)'
        ]
        
        for pattern in location_patterns:
            match = re.search(pattern, text_lower)
            if match:
                location = match.group(1).strip()
                # Clean up common words
                location = re.sub(r'\b(today|tomorrow|now|currently)\b', '', location).strip()
                if location:
                    return location
        
        return None
    
    def get_weather_data(self, location: str = None) -> Dict:
        """Get weather data from Visual Crossing Weather API"""
        try:
            # Use default location if none provided
            if not location:
                location = "Kochi,Kerala,India"
            
            # Visual Crossing API endpoint for current weather
            url = f"{self.base_url}/{location}/today"
            
            params = {
                'key': self.api_key,
                'include': 'current',
                'unitGroup': 'metric',  # Celsius
                'contentType': 'json'
            }
            
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            
            data = response.json()
            
            if 'currentConditions' not in data:
                raise Exception("No current weather data available")
            
            logger.info(f"Weather data retrieved for: {location}")
            return data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Weather API request failed: {e}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"Response status: {e.response.status_code}")
                logger.error(f"Response text: {e.response.text}")
            raise Exception(f"Could not fetch weather data for {location}")
        except Exception as e:
            logger.error(f"Weather processing error: {e}")
            raise
    

    def get_forecast_data(self, location: str) -> dict:
        """
        Fetch tomorrow's forecast from Visual Crossing.
        """
        url = f"https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline/{location}?unitGroup=metric&key={self.api_key}&include=days&elements=datetime,tempmax,tempmin,conditions"
        response = requests.get(url)
        if response.status_code != 200:
            raise Exception(f"Weather API error: {response.text}")
        data = response.json()
        if "days" not in data or len(data["days"]) < 2:
            raise Exception("Tomorrow's forecast not available")
        return data["days"][1]  # index 1 = tomorrow


    def format_weather_response(self, weather_data: Dict, location: str = None) -> str:
        """Format weather data into Zody's cheerful response"""
        try:
            # Extract data from Visual Crossing API response
            current = weather_data['currentConditions']
            location_name = weather_data.get('resolvedAddress', location or 'your location')
            
            temp = round(current['temp'])
            feels_like = round(current['feelslike'])
            humidity = round(current['humidity'])
            conditions = current['conditions']
            wind_speed = round(current['windspeed'], 1)
            visibility = current.get('visibility', 'N/A')
            
            # Get current time info
            current_time = datetime.now().strftime("%I:%M %p")
            
            # Zody's cheerful personality responses based on temperature
            temp_comment = ""
            if temp > 35:
                temp_comment = "Whoa! It's really hot out there! Stay cool and drink plenty of water!"
            elif temp > 25:
                temp_comment = "Nice and warm! Perfect weather to be outside!"
            elif temp > 15:
                temp_comment = "Pleasant temperature! Great for a walk or outdoor activities!"
            elif temp > 5:
                temp_comment = "A bit chilly! You might want a jacket!"
            else:
                temp_comment = "Brrr! It's quite cold! Bundle up and stay warm!"
            
            # Weather condition comments
            condition_comment = ""
            conditions_lower = conditions.lower()
            if 'rain' in conditions_lower:
                condition_comment = " Don't forget your umbrella!"
            elif 'sunny' in conditions_lower or 'clear' in conditions_lower:
                condition_comment = " What a beautiful day!"
            elif 'cloudy' in conditions_lower:
                condition_comment = " Nice cloudy weather!"
            elif 'snow' in conditions_lower:
                condition_comment = " Snow day! Stay safe and warm!"
            
            response = f"""Hi there! I'm Zody, your cheerful robotic weather assistant! Here's the current weather update for {location_name}:

🌤️ Current Conditions: {conditions}
🌡️ Temperature: {temp}°C (feels like {feels_like}°C)
💧 Humidity: {humidity}%
💨 Wind Speed: {wind_speed} km/h
👀 Visibility: {visibility} km
⏰ Updated: {current_time}

{temp_comment}{condition_comment}

Hope this helps you plan your day! Need weather info for somewhere else? Just ask me!"""
            
            return response
            
        except KeyError as e:
            logger.error(f"Missing weather data field: {e}")
            logger.error(f"Available data: {weather_data.keys()}")
            if 'currentConditions' in weather_data:
                logger.error(f"Current conditions keys: {weather_data['currentConditions'].keys()}")
            return "I'm sorry, I couldn't get complete weather information right now. The weather service might be temporarily unavailable. Please try again!"
        except Exception as e:
            logger.error(f"Weather formatting error: {e}")
            return "Oops! I had trouble processing the weather data. Let me try again in a moment!"
    
    def format_forecast_response(self, location: str, forecast_data: dict) -> str:
        """
        Format tomorrow's forecast into Zody's persona style.
        """
        date = forecast_data.get("datetime", "tomorrow")
        tempmax = forecast_data.get("tempmax")
        tempmin = forecast_data.get("tempmin")
        condition = forecast_data.get("conditions", "unknown")

        response = (
            f"Beep-boop 🔮 Scanning the skies for tomorrow in {location} ({date})...\n"
            f"Expect {condition.lower()} with temperatures between {tempmin}°C and {tempmax}°C.\n"
        )

        if "rain" in condition.lower():
            response += "Better grab an umbrella, human! ☔🤖"
        elif "sun" in condition.lower() or "clear" in condition.lower():
            response += "Sunglasses mode activated 😎 Beep-boop!"
        elif "cloud" in condition.lower():
            response += "Clouds detected ☁️ Perfect for cozy mode."
        else:
            response += "Weather sensors calibrated. Stay prepared, human!"

        return response



    def get_weather_response(self, user_query: str) -> str:
        """
        Main entry: decide whether to give current weather or tomorrow's forecast.
        """
        location = self.extract_location(user_query) or "Kochi,Kerala,India"

        try:
            if self.detect_forecast_request(user_query):
                forecast_data = self.get_forecast_data(location)
                return self.format_forecast_response(location, forecast_data)
            else:
                weather_data = self.get_weather_data(location)
                return self.format_weather_response(weather_data, location)
        except Exception as e:
            return f"Beep-boop ⚠️ Weather sensors failed: {str(e)}"

    def detect_forecast_request(self, text: str) -> bool:
        """Return True if user asks about tomorrow's weather."""
        return "tomorrow" in (text or "").lower()
