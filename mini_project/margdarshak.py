import hashlib
import time 
import json
import math
import os
import secrets
import sqlite3
import urllib.error
import urllib.request
from datetime import datetime
from typing import Optional, Tuple
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from groq import Groq, APIConnectionError
try:
    from streamlit_js_eval import streamlit_js_eval
except ImportError:
    streamlit_js_eval = None

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    chrome_options = Options()
except ImportError:
    webdriver = None
    Options = None
    chrome_options = None

load_dotenv()
YOUR_GROQ_KEY = os.getenv("GROQ_API_KEY", "").strip()
AI_ENABLED = bool(YOUR_GROQ_KEY)
client = None
if AI_ENABLED:
    try:
        client = Groq(api_key=YOUR_GROQ_KEY)
        print("Success: Groq Client initialized.")
    except Exception as e:
        print(f"Error: {e}")
        AI_ENABLED = False
    

# --- CONFIGURATION & STYLING ---
st.set_page_config(
    page_title="Margdarshak: Career Advisor",
    layout="wide",
    initial_sidebar_state="expanded",
)

HERO_IMAGE = (
    "https://images.unsplash.com/photo-1523240795612-9a054b0db644"
    "?auto=format&fit=crop&w=1200&q=80"
)

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(APP_DIR, "margdarshak_users.db")

# Reference coordinates for major Indian cities (for "nearby" when user picks city)
CITY_COORDS = {
    "Mumbai": (19.0760, 72.8777),
    "Delhi NCR": (28.6139, 77.2090),
    "Bengaluru": (12.9716, 77.5946),
    "Hyderabad": (17.3850, 78.4867),
    "Chennai": (13.0827, 80.2707),
    "Kolkata": (22.5726, 88.3639),
    "Pune": (18.5204, 73.8567),
    "Ahmedabad": (23.0225, 72.5714),
    "Jaipur": (26.9124, 75.7873),
    "Lucknow": (26.8467, 80.9462),
    "Patna": (25.5941, 85.1376),
    "Bhopal": (23.2599, 77.4126),
    "Kochi": (9.9312, 76.2673),
    "Chandigarh": (30.7333, 76.7794),
}

# --- COLLEGE DATA: loaded from CSV ---
COLLEGE_CSV_PATH = os.path.join(APP_DIR, "colleges.csv")

@st.cache_data(show_spinner=False)
def load_college_data() -> list[dict]:
    """Load college data from colleges.csv next to this script.
    Falls back to an empty list with a clear error if the file is missing or malformed.
    Required columns: name, type, city, state, mainstream, lat, lon, Facilities
    """
    if not os.path.exists(COLLEGE_CSV_PATH):
        st.error(
            f"colleges.csv not found at: `{COLLEGE_CSV_PATH}`\n\n"
            "Please place the CSV file in the same folder as this script.\n"
            "Required columns: name, type, city, state, mainstream, lat, lon, Facilities"
        )
        return []
    try:
        df = pd.read_csv(COLLEGE_CSV_PATH, dtype={
            "name": str, "type": str, "city": str,
            "state": str, "mainstream": str, "Facilities": str
        })
        required = {"name", "type", "city", "state", "mainstream", "lat", "lon", "Facilities"}
        missing = required - set(df.columns)
        if missing:
            st.error(f"colleges.csv is missing columns: {', '.join(sorted(missing))}")
            return []
        df["lat"]  = pd.to_numeric(df["lat"].astype(str).str.strip(),  errors="coerce")
        df["lon"] = pd.to_numeric(df["lon"].astype(str).str.strip(), errors="coerce")
        df = df.dropna(subset=["lat", "lon"])
        return df.to_dict(orient="records")
    except Exception as e:
        st.error(f"Failed to load colleges.csv: {e}")
        return []

COLLEGE_DATA = load_college_data()

# Career pathways: role, skills, recognised professional (illustrative)
CAREER_PATHWAYS = {
    "Science": [
        {
            "role": "Data Scientist",
            "skills": "Python/R, SQL, statistics, machine learning, data visualisation, domain thinking",
            "professional": "Andrew Ng (AI education) — in India, leaders like N. R. Narayana Murthy inspire rigour in tech-driven science careers.",
        },
        {
            "role": "Doctor (Physician)",
            "skills": "Biology depth, NEET PG readiness, clinical reasoning, empathy, lifelong learning",
            "professional": "Dr. Devi Shetty — cardiac surgeon and accessible healthcare advocate.",
        },
        {
            "role": "Engineer (R&D / Core)",
            "skills": "Physics/math fundamentals, design tools, safety standards, teamwork, communication",
            "professional": "Dr. A. P. J. Abdul Kalam — exemplified research-to-deployment in defence & space.",
        },
        {
            "role": "Research Scholar",
            "skills": "Literature review, experimentation, academic writing, grants, conference presentation",
            "professional": "Prof. C. N. R. Rao — materials science leadership and publication excellence.",
        },
        {
            "role": "ISRO / DRDO pathway",
            "skills": "GATE / relevant technical depth, clearance procedures, systems thinking, patriotism & ethics",
            "professional": "K. Sivan — former ISRO Chairman; trajectory from humble roots to national missions.",
        },
    ],
    "Commerce": [
        {
            "role": "Chartered Accountant",
            "skills": "Accounting standards, taxation, audit, ethics, Excel, CA Final discipline",
            "professional": "T. N. Manoharan — former ICAI President; model of integrity in the profession.",
        },
        {
            "role": "Investment Banker / Equity Research",
            "skills": "Financial modelling, valuation, Excel, markets awareness, communication under pressure",
            "professional": "Naina Lal Kidwai — banking and policy voice for Indian finance.",
        },
        {
            "role": "MBA (Strategy / Ops)",
            "skills": "CAT/XAT/GMAT reasoning, case analysis, leadership stories, stakeholder management",
            "professional": "Indra Nooyi — global CEO narrative built on strong commercial education.",
        },
        {
            "role": "UPSC (Economics / Finance services)",
            "skills": "Current affairs, essay, optional depth, answer writing discipline, ethics case studies",
            "professional": "Tina Dabi (IAS) — young achiever; illustrates structured long-horizon preparation.",
        },
        {
            "role": "Entrepreneurship",
            "skills": "Unit economics, fundraising basics, product-market fit, hiring, compliance basics",
            "professional": "Ghazal Alagh (Mamaearth) — D2C scale story grounded in brand and ops.",
        },
    ],
    "Arts": [
        {
            "role": "Civil Services (IAS/IPS)",
            "skills": "GS papers, optional mastery, essay, interview poise, ethical reasoning",
            "professional": "S. R. Sankaran (IAS) — remembered for pro-people administration.",
        },
        {
            "role": "Journalism",
            "skills": "Fact-checking, storytelling, digital tools, media law awareness, speed with accuracy",
            "professional": "Ravish Kumar — long-form TV journalism with public interest focus.",
        },
        {
            "role": "Lawyer (Litigation / Corporate)",
            "skills": "Legal research, drafting, AIBE/court craft, client communication, patience",
            "professional": "Fali S. Nariman — constitutional and corporate law eminence.",
        },
        {
            "role": "Social Work / NGO leadership",
            "skills": "Community mobilisation, fundraising, programme M&E, empathy, local language",
            "professional": "Elaben Bhatt (SEWA) — organised informal women workers at scale.",
        },
        {
            "role": "Teaching / Academia",
            "skills": "Subject mastery, pedagogy, classroom management, B.Ed./NET as relevant, curiosity",
            "professional": "Dr. Sarvepalli Radhakrishnan — philosopher-teacher; Teachers' Day namesake.",
        },
    ],
    "Vocational": [
        {
            "role": "Skilled Technician (Industry 4.0)",
            "skills": "NSQF alignment, CNC / electrical basics, safety, Kaizen mindset",
            "professional": "Japan's 'Monozukuri' craftsmen — global benchmark for skill pride (adapt to ITI/polytechnic paths).",
        },
        {
            "role": "Graphic / UX Designer",
            "skills": "Figma/Adobe, typography, colour theory, portfolio, client feedback loops",
            "professional": "Paula Scher — identity design authority; study portfolios on Behance/Dribbble.",
        },
        {
            "role": "Digital Marketing Specialist",
            "skills": "SEO/SEM, analytics, content calendars, A/B testing, ROI reporting",
            "professional": "Neil Patel — prolific educator on measurable growth marketing.",
        },
        {
            "role": "Nursing / Allied Health",
            "skills": "Patient care protocols, empathy, shift discipline, licensing exams where applicable",
            "professional": "Florence Nightingale — foundation of evidence-based nursing practice.",
        },
    ],
}

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(min(1.0, a)))


def fetch_ip_location():
    """Approximate lat/lon from outbound IP (works well on a home PC; on cloud it is server region)."""
    for url in (
        "https://ipapi.co/json/",
        "http://ip-api.com/json/?fields=status,lat,lon,city,regionName",
    ):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Margdarshak/1.0"})
            with urllib.request.urlopen(req, timeout=6) as resp:
                data = json.loads(resp.read().decode())
            if "latitude" in data and data.get("latitude") is not None:
                lat, lon = float(data["latitude"]), float(data["longitude"])
                city = data.get("city") or ""
                return lat, lon, city
            if data.get("status") == "success":
                return float(data["lat"]), float(data["lon"]), data.get("city", "")
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, KeyError, TypeError):
            continue
    return None


def get_user_coords(
    method: str,
    city_key: str,
    manual_lat: float,
    manual_lon: float,
) -> tuple[float, float, str]:
    label = ""
    if method == "City":
        lat, lon = CITY_COORDS[city_key]
        return lat, lon, city_key
    if method == "GPS coordinates (from your device / maps)":
        return manual_lat, manual_lon, "Your coordinates"
    if method == "Approximate (network IP)":
        ip = fetch_ip_location()
        if ip is None:
            raise RuntimeError("Could not detect location from IP. Try city or GPS.")
        lat, lon, city = ip
        label = f"IP ~ {city}" if city else "IP-based"
        return lat, lon, label or "IP-based"
    raise ValueError("Unknown location method")


def get_device_gps_result(request_id: int) -> Optional[dict]:
        """
        Fetch browser/device GPS coordinates via browser API.
        Returns a dict with status fields, or None while waiting for JS resolution.
        """
        if streamlit_js_eval is None:
                return None

        js_expr = """
        await new Promise((resolve) => {
            if (!navigator.geolocation) {
                resolve(JSON.stringify({ status: 'unsupported' }));
                return;
            }
            navigator.geolocation.getCurrentPosition(
                (pos) => resolve(JSON.stringify({
                    status: 'ok',
                    latitude: pos.coords.latitude,
                    longitude: pos.coords.longitude,
                    accuracy: pos.coords.accuracy
                })),
                (err) => resolve(JSON.stringify({
                    status: 'error',
                    code: err.code,
                    message: err.message
                })),
                { enableHighAccuracy: false, timeout: 15000, maximumAge:6000 }
            );
        })
        """

        raw = streamlit_js_eval(js_expressions=js_expr, key=f"device_gps_fetch_{request_id}")
        if not raw:
                return None
        try:
                parsed = json.loads(raw) if isinstance(raw, str) else raw
                if not isinstance(parsed, dict):
                        return None
                return parsed
        except (ValueError, TypeError, KeyError):
                return None


# --- AUTH (SQLite) ---
def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash BLOB NOT NULL,
                salt BLOB NOT NULL,
                full_name TEXT NOT NULL,
                email TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.commit()


def _hash_password(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 210_000)


def register_user(username: str, password: str, full_name: str, email: str) -> tuple[bool, str]:
    username = username.strip().lower()
    if not username or len(username) < 3:
        return False, "Username must be at least 3 characters."
    if len(password) < 6:
        return False, "Password must be at least 6 characters."
    salt = secrets.token_bytes(16)
    ph = _hash_password(password, salt)
    now = datetime.utcnow().isoformat() + "Z"
    try:
        with _db() as conn:
            conn.execute(
                "INSERT INTO users (username, password_hash, salt, full_name, email, created_at) VALUES (?,?,?,?,?,?)",
                (username, ph, salt, full_name.strip(), email.strip(), now),
            )
            conn.commit()
    except sqlite3.IntegrityError:
        return False, "That username is already taken."
    return True, "Account created. You can log in now."


def verify_login(username: str, password: str) -> tuple[bool, str | None, dict | None]:
    username = username.strip().lower()
    with _db() as conn:
        row = conn.execute(
            "SELECT username, password_hash, salt, full_name, email FROM users WHERE username = ?",
            (username,),
        ).fetchone()
    if row is None:
        return False, "Invalid username or password.", None
    salt = row["salt"]
    expected = row["password_hash"]
    if secrets.compare_digest(_hash_password(password, salt), expected):
        return True, None, {
            "username": row["username"],
            "full_name": row["full_name"],
            "email": row["email"],
        }
    return False, "Invalid username or password.", None


def auth_sidebar() -> None:
    if "auth_user" not in st.session_state:
        st.session_state.auth_user = None

    st.sidebar.markdown("### Account")
    if st.session_state.auth_user:
        u = st.session_state.auth_user
        st.sidebar.success(f"Signed in as **{u['username']}**")
        if st.sidebar.button("Log out", key="logout_btn"):
            st.session_state.auth_user = None
            st.rerun()
    else:
        tab_login, tab_reg = st.sidebar.tabs(["Log in", "Register"])
        with tab_login:
            lu = st.text_input("Username", key="login_user")
            lp = st.text_input("Password", type="password", key="login_pass")
            if st.button("Log in", key="login_submit"):
                ok, err, profile = verify_login(lu, lp)
                if ok and profile:
                    st.session_state.auth_user = profile
                    st.rerun()
                else:
                    st.error(err or "Login failed.")
        with tab_reg:
            ru = st.text_input("Choose username", key="reg_user")
            rn = st.text_input("Full name", key="reg_name")
            re = st.text_input("Email", key="reg_email")
            rp = st.text_input("Password", type="password", key="reg_pass")
            rp2 = st.text_input("Confirm password", type="password", key="reg_pass2")
            if st.button("Create account", key="reg_submit"):
                if rp != rp2:
                    st.error("Passwords do not match.")
                else:
                    ok, msg = register_user(ru, rp, rn, re)
                    if ok:
                        st.success(msg)
                    else:
                        st.error(msg)


# --- AI LOGIC ---
@st.cache_data(show_spinner=False) # This saves the result so you don't call the API twice for the same input
def get_ai_recommendation(q1, q2, q3, q4, q5, q6) -> str:
    if not AI_ENABLED or client is None:
        return "AI is not configured. Please add a valid GROQ_API_KEY to your .env file."

    prompt = f"""
    You are an expert Indian Career Counselor. A student provided these details:
    - Primary Interest: {q1}
    - Career Goal: {q2}
    - Favorite Subject Stream: {q3}
    - Preferred Work Style: {q4}
    - Study Preference: {q5}
    - Long-term Career Aspiration: {q6}

    Provide a response in these 3 clear sections:
    1. RECOMMENDED STREAM: Identify the best fit (Science/Commerce/Arts/Vocational).
    2. 2026 EXAM PATHWAY: List specific entrance exams they should target in 2026 
       (e.g., JEE Jan/April sessions, NEET May 3rd, CUET May 11-31, NDA April/Sept, CLAT, or SSC CHSL).
    3. TOP 5 CAREERS: 5 specific careers with a 1-sentence explanation for each.
    
    Keep the tone encouraging and professional.
    """

    try:
        # Groq uses the chat.completions format
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            model="llama-3.3-70b-versatile", # High-quality model
            temperature=0.7,
        )
        content = chat_completion.choices[0].message.content
        return content if content is not None else "AI returned an empty response. Please try again."
    except TypeError as e:
        return f"Response parsing error from AI: {e}"
    except APIConnectionError as e:
        return f"Network error — check your internet connection: {e}"
    except AttributeError as e:
        return f"Unexpected response format from AI: {e}"
    except Exception as e:
        return f"Groq AI request failed: {e}"
    

def _inject_theme_css() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600;700&family=Source+Sans+3:wght@400;500;600&display=swap');

        html, body, [class*="css"] { font-family: 'Source Sans 3', sans-serif; }
        .stApp {
            background:
              linear-gradient(165deg, rgba(253, 250, 245, 0.97) 0%, rgba(245, 238, 228, 0.95) 45%, rgba(232, 245, 236, 0.92) 100%),
              url("https://images.unsplash.com/photo-1497633762265-9d179a990aa6?auto=format&fit=crop&w=2000&q=60");
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
        }
        [data-testid="stHeader"] { background: rgba(255,255,255,0.65); backdrop-filter: blur(8px); }
        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #1a2332 0%, #0f1419 100%) !important;
            border-right: 1px solid rgba(255,255,255,0.06);
        }
        [data-testid="stSidebar"] [data-baseweb="radio"] label {
            color: #fff !important;
        }
        [data-testid="stSidebar"] .stMarkdown {
            color: #fff !important;
        }
        [data-testid="stSidebar"] button[role="tab"],
        [data-testid="stSidebar"] button[role="tab"] p {
            color: #fff !important;
        }
        h1, h2, h3 { font-family: 'Fraunces', Georgia, serif !important; letter-spacing: -0.02em; }
        .margdarshak-hero {
            border-radius: 20px;
            padding: 1.75rem 2rem;
            margin-bottom: 1.5rem;
            background: linear-gradient(135deg, rgba(26, 107, 69, 0.12) 0%, rgba(232, 99, 26, 0.1) 100%);
            border: 1px solid rgba(26, 24, 20, 0.08);
            box-shadow: 0 12px 40px rgba(26, 35, 50, 0.08);
        }
        .margdarshak-hero h1 { margin: 0 0 0.35rem 0; font-size: clamp(1.6rem, 3vw, 2.1rem); color: #1a2332; }
        .margdarshak-hero p { margin: 0; color: #4a5568; font-size: 1.05rem; line-height: 1.5; }
        .stButton > button {
            background: linear-gradient(135deg, #c75a1a 0%, #e8631a 100%) !important;
            color: #fff !important;
            border: none !important;
            font-weight: 600 !important;
            padding: 0.55rem 1.4rem !important;
            border-radius: 12px !important;
            box-shadow: 0 4px 14px rgba(232, 99, 26, 0.35);
        }
        .stButton > button:hover { filter: brightness(1.05); box-shadow: 0 6px 20px rgba(232, 99, 26, 0.45); }
        </style>
        """,
        unsafe_allow_html=True,
    )


def main():
    init_db()
    _inject_theme_css()

    st.markdown(
        """
        <div class="margdarshak-hero">
          <h1>Margdarshak — Digital Guidance Platform</h1>
          <p>Career counselling, college discovery, and scholarship awareness — built for Indian students.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    auth_sidebar()

    if not AI_ENABLED:
        st.warning("⚠️ AI configuration not found. Set GENAI_API_KEY in your .env and restart.")

    nav_pages = [
        "Home & Aptitude Quiz",
        "College Directory",
        "Career Pathways",
        "Scholarship Tracker",
        "My Profile",
    ]
    sidebar = st.sidebar.radio(
        "Navigation", 
        nav_pages, 
        label_visibility="visible",
        # Trick to font color: use markdown and inject style.
        # Streamlit does not natively support color for radio, so inject CSS:
        help="",
    )
    st.markdown("""
        <style>
        .sidebar-content, .sidebar-content * {
            color: #fff !important;
        }
        [data-testid=stSidebar] label, [data-testid=stSidebar] span, [data-testid=stSidebar] div {
            color: #fff !important;
        }
        </style>
    """, unsafe_allow_html=True)

    if sidebar == "Home & Aptitude Quiz":
        st.subheader("Find your path")
        col_form, col_visual = st.columns([1.15, 1], gap="large")
        with col_form:
            q1 = st.selectbox(
                "What do you enjoy most?",
                ["Solving Puzzles/Math", "Reading/Writing/History", "Managing Money/Business", "Hands-on Practical Work"],
            )
            q2 = st.selectbox(
                "What is your goal?",
                ["High Salary in Corporate", "Serving the Public (Govt)", "Innovation & Research", "Starting a Business"],
            )
            q3 = st.selectbox(
                "Which type of subject do you prefer?",
                ["Math/Science", "Commerce", "Arts", "Vocational"],
            )
            q4 = st.selectbox(
                "What kind of work style suits you?",
                ["Analytical problem-solving", "Creative expression", "People management", "Field/technical hands-on work"],
            )
            q5 = st.selectbox(
                "How do you prefer learning?",
                ["Theory and concepts", "Practical projects", "Case studies and real examples", "A mix of theory and practice"],
            )
            q6 = st.selectbox(
                "What is your long-term aspiration?",
                ["High-impact research/innovation", "Stable government/public service career", "Leadership or entrepreneurship", "Specialized professional expertise"],
            )
            go = st.button("Get AI Recommendation", type="primary")

        with col_visual:
            st.caption("Learning together — your next step matters.")
            st.image(HERO_IMAGE, use_container_width=True, caption="Guidance for every learner")

        if go:
            with st.spinner("Analyzing your profile..."):
                res = get_ai_recommendation(q1, q2, q3, q4, q5, q6)
            st.success("Personalized AI suggestion")
            st.write(res)

            stream_found = next((k for k in CAREER_PATHWAYS if k.lower() in res.lower()), None)
            if stream_found:
                roles = [x["role"] for x in CAREER_PATHWAYS[stream_found]]
                st.info(f"Top careers in **{stream_found}**: {', '.join(roles)}")

    elif sidebar == "College Directory":
        st.header("Nearby colleges & mainstream courses")
        st.caption(
            "Set your present location using device GPS or city. "
            "Distances are straight-line (km) for ranking."
        )

        loc_method = st.radio(
            "How should we place you?",
            [
                "Device GPS (auto, browser permission)",
                "City",
            ],
            horizontal=True,
        )

        city_key = "Mumbai"
        radius_km = st.slider("Search radius (km)", min_value=10, max_value=500, value=120, step=10)

        if "device_gps_coords" not in st.session_state:
            st.session_state.device_gps_coords = None
        if "device_gps_requested" not in st.session_state:
            st.session_state.device_gps_requested = False
        if "device_gps_request_id" not in st.session_state:
            st.session_state.device_gps_request_id = 0
        if "device_gps_attempts" not in st.session_state:
            st.session_state.device_gps_attempts = 0

        def _try_ip_fallback(reason: str):
            """Fall back to IP-based location and store result in session state."""
            st.warning(f"{reason} Trying IP-based location as fallback...")
            ip = fetch_ip_location()
            if ip:
                lat, lon, city = ip
                st.session_state.device_gps_coords = (lat, lon)
                st.success(f"📍 Using IP-based location: {city} ({lat:.5f}, {lon:.5f})")
            else:
                st.error("Could not detect location automatically. Please use **City** mode instead.")

        if loc_method == "Device GPS (auto, browser permission)":
            if streamlit_js_eval is None:
                st.warning("`streamlit-js-eval` not installed. Falling back to IP-based location automatically.")
                if st.session_state.device_gps_coords is None:
                    _try_ip_fallback("streamlit-js-eval unavailable.")
            else:
                st.info("Click below and allow location permission when your browser asks.")
                if st.button("Use my current device location", key="fetch_device_gps"):
                    st.session_state.device_gps_request_id += 1
                    st.session_state.device_gps_requested = True
                    st.session_state.device_gps_coords = None
                    st.session_state.device_gps_attempts = 0

                
                if st.session_state.device_gps_requested:
                    gps_result = get_device_gps_result(st.session_state.device_gps_request_id)

                    if gps_result is None:
                        # JS hasn't resolved yet — keep polling with st.rerun()
                        st.session_state.device_gps_attempts += 1
                        attempts = st.session_state.device_gps_attempts
                        MAX_ATTEMPTS = 10  # ~40 seconds total

                        if attempts <= MAX_ATTEMPTS:
                            st.info(f"⏳ Waiting for browser GPS... ({attempts}/{MAX_ATTEMPTS})")
                            time.sleep(1)
                            st.rerun()
                        else:
                            # Timed out on our end — fall back to IP
                            st.session_state.device_gps_requested = False
                            st.session_state.device_gps_attempts = 0
                            _try_ip_fallback("GPS timed out after 10 seconds.")

                    elif gps_result.get("status") == "ok":
                        lat = float(gps_result["latitude"])
                        lon = float(gps_result["longitude"])
                        st.session_state.device_gps_coords = (lat, lon)
                        st.session_state.device_gps_requested = False
                        st.session_state.device_gps_attempts = 0
                        st.success(f"✅ GPS captured: {lat:.5f}, {lon:.5f}")

                    elif gps_result.get("status") == "unsupported":
                        st.session_state.device_gps_requested = False
                        _try_ip_fallback("This browser does not support geolocation.")

                    else:
                        st.session_state.device_gps_requested = False
                        err_code = gps_result.get("code")
                        if err_code == 1:
                            # User explicitly denied — don't silently fall back, explain clearly
                            st.error(
                                "📍 Location permission denied. Please allow location access in your "
                                "browser settings and click the button again, or switch to **City** mode."
                            )
                        elif err_code == 2:
                            _try_ip_fallback("GPS position unavailable.")
                        elif err_code == 3:
                            _try_ip_fallback("GPS request timed out.")
                        else:
                            _try_ip_fallback("GPS returned an unexpected error.")

                # Show current GPS coords if already captured
                if st.session_state.device_gps_coords is not None and not st.session_state.device_gps_requested:
                    lat, lon = st.session_state.device_gps_coords
                    st.caption(f"📌 Current location: {lat:.5f}, {lon:.5f}")

        if loc_method == "City":
            city_key = st.selectbox("Your city / region", list(CITY_COORDS.keys()))

        if st.button("Show colleges near me", type="primary"):
            try:
                if loc_method == "Device GPS (auto, browser permission)":
                    if st.session_state.device_gps_coords is None:
                        raise RuntimeError("Device GPS not set yet. Click 'Use my current device location' first.")
                    ulat, ulon = st.session_state.device_gps_coords
                    loc_label = "Device GPS"
                else:
                    ulat, ulon, loc_label = get_user_coords(loc_method, city_key, 0.0, 0.0)
                st.success(f"Using location: **{loc_label}** ({ulat:.4f}°, {ulon:.4f}°)")
                rows = []
                for c in COLLEGE_DATA:
                    d_km = haversine_km(ulat, ulon, c["lat"], c["lon"])
                    rows.append(
                        {
                            "Distance (km)": round(d_km, 1),
                            "Name": c["name"],
                            "Type": c["type"],
                            "City": c["city"],
                            "State": c["state"],
                            "Mainstream courses": c["mainstream"],
                            "Facilities": c["Facilities"],
                            "Google Maps": f"https://www.google.com/maps/dir/?api=1&origin={ulat},{ulon}&destination={c['lat']},{c['lon']}",
                            "lat": c["lat"],
                            "lon": c["lon"],
                        }
                    )
                rows.sort(key=lambda x: x["Distance (km)"])
                nearby_rows = [r for r in rows if r["Distance (km)"] <= radius_km]
                if not nearby_rows:
                    st.warning(
                        f"No college found within {radius_km} km. Showing 5 nearest colleges instead."
                    )
                    nearby_rows = rows[:5]

                result_df = pd.DataFrame(nearby_rows)
                st.dataframe(
                    result_df.drop(columns=["lat", "lon"]),
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Google Maps": st.column_config.LinkColumn(
                            "Google Maps route",
                            display_text="Open route",
                        )
                    },
                )

                
            except RuntimeError as e:
                st.error(str(e))
            except Exception as e:
                st.error(f"Could not resolve location: {e}")

    elif sidebar == "Career Pathways":
        st.header("Course-to-career mapping")
        st.caption("Each pathway lists core skills and a recognised professional for inspiration.")
        stream = st.selectbox("Choose a stream", list(CAREER_PATHWAYS.keys()))
        for item in CAREER_PATHWAYS[stream]:
            with st.expander(f"**{item['role']}**", expanded=False):
                st.markdown(f"**Skills to build:** {item['skills']}")
                st.markdown(f"**Success profile:** {item['professional']}")

    elif sidebar == "Scholarship Tracker":
        st.header("2026 Scholarship & Financial Aid")

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("National Schemes")
            st.success(
                "**Central Sector Scheme (CSSS)**\n- Eligibility: Top 20th percentile of Class 12.\n- Amount: ₹12,000/yr (UG), ₹20,000/yr (PG)."
            )
            st.info(
                "**PM Scholarship Scheme (PMSS)**\n- For wards of Ex-servicemen/Police.\n- Amount: ₹30,000 - ₹36,000 annually."
            )

        with col2:
            st.subheader("Upcoming Deadlines")
            st.warning("⚠️ **NSP Portal (National Scholarship):** Typically opens July-August.")
            st.error("🚨 **SBI Asha Scholarship:** Applications close March/April 2026.")

        st.markdown("---")
        st.write(
            "💡 *Tip: Keep your Income Certificate and Aadhaar-seeded bank account ready for DBT (Direct Benefit Transfer).*"
        )

    elif sidebar == "My Profile":
        st.header("My profile")
        if st.session_state.auth_user is None:
            st.info("Use **Log in** or **Register** in the sidebar under **Account**.")
        else:
            u = st.session_state.auth_user
            st.subheader("Your account")
            st.write(f"**Username:** {u['username']}")
            st.write(f"**Full name:** {u['full_name']}")
            st.write(f"**Email:** {u['email']}")
            st.caption("To change details, contact support or re-register a new account (delete old row in DB for production apps).")


if __name__ == "__main__":
    main()
