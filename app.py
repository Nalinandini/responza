import os
import logging
from flask import Flask, render_template, request, redirect, url_for
from twilio.rest import Client
from dotenv import load_dotenv
import database

# Load environment variables from .env file
load_dotenv()

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger("responza")

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'responza-default-key-change-in-prod')

# Initialize SQLite database
database.init_db()

# Read Twilio credentials securely from environment variables
TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')
TWILIO_PHONE_NUMBER = os.environ.get('TWILIO_PHONE_NUMBER')
ALERT_PHONE_NUMBER = os.environ.get('ALERT_PHONE_NUMBER', '+918499955374')

# Initialize Twilio Client safely without crashing on missing/placeholder credentials
twilio_client = None
if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
    # Check if credentials are not default placeholders
    if not (TWILIO_ACCOUNT_SID.startswith("your_") or TWILIO_AUTH_TOKEN.startswith("your_")):
        try:
            twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
            logger.info("Twilio client initialized successfully.")
        except Exception as e:
            logger.error("Failed to initialize Twilio client: %s", e)
    else:
        logger.warning("Twilio credentials appear to be placeholders. SMS dispatch will run in simulation mode.")
else:
    logger.warning("Twilio environment variables not set. SMS dispatch will run in simulation mode.")

# Supported languages
SUPPORTED_LANGUAGES = ['en', 'te', 'hi']

# Emergency guidance data with translations and dial links
emergency_data = {
    'en': {
        'Chest Pain': {
            'steps': [
                "Loosen tight clothing.",
                "Help the person sit down and rest in a comfortable position.",
                "Call emergency medical services immediately (Dial 108)."
            ],
            'call': 'tel:108'
        },
        'Road Accident': {
            'steps': [
                "Call ambulance immediately (Dial 108).",
                "Check if the injured person is breathing.",
                "Do not move the injured person unless there is immediate danger."
            ],
            'call': 'tel:108'
        },
        'Fire': {
            'steps': [
                "Evacuate the area immediately via nearest fire exit.",
                "Use a certified fire extinguisher only if trained.",
                "Call fire and rescue services (Dial 101)."
            ],
            'call': 'tel:101'
        },
        'Cyber Crime': {
            'steps': [
                "Report immediately online at cybercrime.gov.in.",
                "Preserve all evidence (screenshots, transaction receipts, messages).",
                "Call national cybercrime helpline (Dial 1930)."
            ],
            'call': 'tel:1930'
        },
        'Domestic Violence': {
            'steps': [
                "Ensure you and any dependents are in a safe location.",
                "Call national helpline number 181 or 1091.",
                "Document or report the incident to authorities when safe."
            ],
            'call': 'tel:181'
        },
        'Suspicious Activity': {
            'steps': [
                "Remain calm and maintain a safe distance.",
                "Note down identifying details, vehicle numbers, or appearances.",
                "Report directly to police emergency services (Dial 100)."
            ],
            'call': 'tel:100'
        },
        'Medical Emergency': {
            'steps': [
                "Stay calm and assess the individual's responsiveness.",
                "Call 108 immediately for an ambulance.",
                "Administer certified first aid / CPR if trained."
            ],
            'call': 'tel:108'
        }
    },
    'te': {
        'గుండె పోటు': {
            'steps': [
                "టైట్ గల దుస్తులను తులిపేయండి.",
                "వారు కూర్చునేలా చేసి విశ్రాంతినివ్వండి.",
                "తక్షణమే 108 నెంబర్‌కు కాల్ చేయండి."
            ],
            'call': 'tel:108'
        },
        'రోడ్ యాక్సిడెంట్': {
            'steps': [
                "108 నెంబర్‌కు కాల్ చేయండి.",
                "వ్యక్తి ఊపిరి తీసుకుంటున్నారా చూడు.",
                "అవసరమైతే తప్ప బాధితుడిని కదల్చకండి."
            ],
            'call': 'tel:108'
        },
        'అగ్ని ప్రమాదం': {
            'steps': [
                "ప్రాంతాన్ని వెంటనే విడిచిపెట్టండి.",
                "ఫైర్ ఎక్స్టింగ్విషర్ ఉపయోగించండి (అవగాహన ఉంటే).",
                "101 నెంబర్‌కు కాల్ చేయండి."
            ],
            'call': 'tel:101'
        },
        'సైబర్ నేరాలు': {
            'steps': [
                "cybercrime.gov.in లో నివేదిక ఇవ్వండి.",
                "సాక్ష్యాలను సేవ్ చేయండి.",
                "1930 నెంబర్‌కు కాల్ చేయండి."
            ],
            'call': 'tel:1930'
        },
        'గృహ హింస': {
            'steps': [
                "మీరు సురక్షితమైన ప్రదేశంలో ఉన్నారా చూసుకోండి.",
                "హెల్ప్‌లైన్ నంబర్ 181 లేదా 1091 కు కాల్ చేయండి.",
                "సాధ్యమైనట్లయితే వివరాలు రికార్డు చేయండి."
            ],
            'call': 'tel:181'
        },
        'అనుమానాస్పద కార్యకలాపం': {
            'steps': [
                "నిర్మలంగా ఉండండి మరియు సురక్షితంగా ఉండండి.",
                "వివరాలు గమనించండి.",
                "100 కు కాల్ చేసి పోలీసులకు తెలియజేయండి."
            ],
            'call': 'tel:100'
        },
        'వైద్య అత్యవసర': {
            'steps': [
                "స్థితిని అంచనా వేయండి.",
                "108 కు కాల్ చేయండి.",
                "ఫస్ట్ ఎయిడ్ ఇవ్వండి (తెలిసినట్లయితే)."
            ],
            'call': 'tel:108'
        }
    },
    'hi': {
        'सीने में दर्द': {
            'steps': [
                "कसे हुए कपड़े ढीले करें।",
                "व्यक्ति को बैठाएं और आराम दें।",
                "108 पर कॉल करें।"
            ],
            'call': 'tel:108'
        },
        'सड़क दुर्घटना': {
            'steps': [
                "तुरंत एम्बुलेंस को कॉल करें (108)।",
                "व्यक्ति की साँसों की जांच करें।",
                "जब तक ज़रूरी न हो, घायल को न हिलाएं।"
            ],
            'call': 'tel:108'
        },
        'आग': {
            'steps': [
                "तुरंत बाहर निकलें।",
                "फायर एक्सटिंग्विशर का उपयोग करें (अगर जानते हों)।",
                "101 पर कॉल करें।"
            ],
            'call': 'tel:101'
        },
        'साइबर क्राइम': {
            'steps': [
                "cybercrime.gov.in पर रिपोर्ट करें।",
                "स्क्रीनशॉट्स और सबूत सुरक्षित रखें।",
                "1930 पर कॉल करें।"
            ],
            'call': 'tel:1930'
        },
        'घरेलू हिंसा': {
            'steps': [
                "सुरक्षित स्थान पर जाएँ।",
                "181 या 1091 पर कॉल करें।",
                "अगर संभव हो तो साक्ष्य सुरक्षित करें।"
            ],
            'call': 'tel:181'
        },
        'संदिग्ध गतिविधि': {
            'steps': [
                "शांत रहें और सुरक्षित रहें।",
                "जानकारी नोट करें।",
                "100 पर कॉल करें।"
            ],
            'call': 'tel:100'
        },
        'चिकित्सा आपातकाल': {
            'steps': [
                "स्थिति का मूल्यांकन करें।",
                "108 पर कॉल करें।",
                "प्रशिक्षित हैं तो प्राथमिक चिकित्सा दें।"
            ],
            'call': 'tel:108'
        }
    }
}

def sanitize_language(lang_input: str) -> str:
    """Validate requested language against supported list."""
    if lang_input in SUPPORTED_LANGUAGES:
        return lang_input
    return 'en'

def validate_coordinates(lat_str, lon_str):
    """
    Validate latitude and longitude values safely.
    Returns (lat_float, lon_float, location_url)
    """
    try:
        if not lat_str or not lon_str:
            return None, None, "Location unavailable."
        
        lat = float(lat_str)
        lon = float(lon_str)

        # Validate geographic bounds
        if -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0:
            location_url = f"https://maps.google.com/?q={lat:.6f},{lon:.6f}"
            return round(lat, 6), round(lon, 6), location_url
        else:
            logger.warning("Coordinates out of valid range: lat=%s, lon=%s", lat, lon)
            return None, None, "Location unavailable."
    except (ValueError, TypeError) as err:
        logger.warning("Invalid coordinate values provided: %s, %s (Error: %s)", lat_str, lon_str, err)
        return None, None, "Location unavailable."


# ==============================================================================
# ROUTE 1: Splash Screen (Entry point ONLY)
# ==============================================================================
@app.route('/', methods=['GET'])
def splash():
    """Renders the splash screen with automatic navigation to /home."""
    return render_template('splash.html')


# ==============================================================================
# ROUTE 2: Home Page (Main application dashboard)
# ==============================================================================
@app.route('/home', methods=['GET', 'POST'])
def home():
    """Main dashboard handling language selection and emergency listing."""
    if request.method == 'POST':
        language = sanitize_language(request.form.get('language', 'en'))
    else:
        language = sanitize_language(request.args.get('language', 'en'))

    emergency_list = list(emergency_data[language].keys())
    return render_template('index.html', language=language, emergency_list=emergency_list)


# ==============================================================================
# ROUTE 3: Emergency Guidance Handler
# ==============================================================================
@app.route('/handle_emergency', methods=['POST'])
def handle_emergency():
    """Validates inputs and displays emergency steps with call and SMS options."""
    language = sanitize_language(request.form.get('language', 'en'))
    selected = request.form.get('emergency', '').strip()

    category_dict = emergency_data.get(language, {})
    if selected not in category_dict:
        logger.warning("Invalid emergency requested: %s for language: %s", selected, language)
        return redirect(url_for('home', language=language))

    data = category_dict[selected]
    return render_template(
        'response.html',
        language=language,
        selected=selected,
        steps=data['steps'],
        call_link=data['call']
    )


# ==============================================================================
# ROUTE 4: Emergency SMS Dispatcher
# ==============================================================================
@app.route('/send_sms', methods=['POST'])
def send_sms():
    """Dispatches emergency SMS alert via Twilio, persists record to SQLite."""
    language = sanitize_language(request.form.get('language', 'en'))
    emergency = request.form.get('emergency', 'Emergency Situation').strip()
    lat_input = request.form.get('latitude')
    lon_input = request.form.get('longitude')

    # Validate coordinates
    latitude, longitude, location_url = validate_coordinates(lat_input, lon_input)

    # Compose alert message
    message_body = f"EMERGENCY ALERT: {emergency}\nLocation: {location_url}"
    recipient_number = ALERT_PHONE_NUMBER or '+918499955374'
    masked_recipient = database.mask_phone_number(recipient_number)

    # Localized text dictionaries
    success_texts = {
        'en': '✅ Emergency SMS Alert Dispatched Successfully',
        'te': '✅ అత్యవసర SMS హెచ్చరిక విజయవంతంగా పంపబడింది',
        'hi': '✅ आपातकालीन SMS अलर्ट सफलतापूर्वक भेजा गया'
    }

    back_texts = {
        'en': '⬅ Back to Home',
        'te': '⬅ హోమ్‌కు వెళ్ళు',
        'hi': '⬅ मुख्य पृष्ठ पर जाएँ'
    }

    error_texts = {
        'en': 'We were unable to deliver the automated SMS alert at this moment. Please use the direct call button below immediately.',
        'te': 'ప్రస్తుతం ఆటోమేటిక్ SMS హెచ్చరికను పంపడం సాధ్యం కాలేదు. దయచేసి వెంటనే క్రింద ఉన్న డైరెక్ట్ కాల్ బటన్‌ను ఉపయోగించండి.',
        'hi': 'इस समय स्वचालित SMS अलर्ट नहीं भेजा जा सका। कृपया तुरंत नीचे दिए गए डायरेक्ट कॉल बटन का उपयोग करें।'
    }

    # Determine default call link for backup
    call_link = 'tel:108'
    if language in emergency_data and emergency in emergency_data[language]:
        call_link = emergency_data[language][emergency].get('call', 'tel:108')

    # Twilio dispatch with safe error handling and simulation fallback
    try:
        if twilio_client and TWILIO_PHONE_NUMBER:
            message = twilio_client.messages.create(
                body=message_body,
                from_=TWILIO_PHONE_NUMBER,
                to=recipient_number
            )
            twilio_sid = message.sid
            status = "SUCCESS"
            logger.info("SMS alert sent successfully. SID: %s", twilio_sid)
        else:
            # Simulated mode for development or when Twilio is not configured
            twilio_sid = "SIMULATED_" + os.urandom(4).hex()
            status = "SIMULATED"
            logger.info("SMS alert simulated (Twilio credentials not configured). Payload: %s", message_body)

        # Persist incident in SQLite
        database.log_incident(
            emergency_type=emergency,
            language=language,
            latitude=latitude,
            longitude=longitude,
            location_url=location_url,
            recipient=recipient_number,
            status=status,
            twilio_sid=twilio_sid
        )

        return render_template(
            "send_sms.html",
            is_success=True,
            phone_number=masked_recipient,
            location_url=location_url,
            language=language,
            success_message=success_texts.get(language, success_texts['en']),
            back_message=back_texts.get(language, back_texts['en'])
        )

    except Exception as exc:
        # Log internal technical error securely on the server
        logger.error("Failed to send emergency SMS via Twilio: %s", exc, exc_info=True)

        # Persist failed attempt to SQLite with masked recipient
        database.log_incident(
            emergency_type=emergency,
            language=language,
            latitude=latitude,
            longitude=longitude,
            location_url=location_url,
            recipient=recipient_number,
            status="FAILED",
            error_message="SMS delivery failure"
        )

        # Render friendly localized error without exposing raw exception details
        return render_template(
            "send_sms.html",
            is_success=False,
            phone_number=masked_recipient,
            location_url=location_url,
            language=language,
            error_message=error_texts.get(language, error_texts['en']),
            call_link=call_link,
            back_message=back_texts.get(language, back_texts['en'])
        )


# ==============================================================================
# ROUTE 5: Incident History (Persistent Storage Viewer)
# ==============================================================================
@app.route('/history', methods=['GET'])
def incident_history():
    """Displays stored emergency incident reports with privacy protections."""
    incidents = database.get_incidents(limit=50)
    return render_template('history.html', incidents=incidents)


# ==============================================================================
# Application Server Entry Point
# ==============================================================================
if __name__ == '__main__':
    # Disable Flask debug mode in production (configurable via FLASK_DEBUG env var)
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() in ('true', '1', 't')
    logger.info("Starting Responza application on http://0.0.0.0:5000 (debug=%s)", debug_mode)
    app.run(host='0.0.0.0', port=5000, debug=debug_mode)