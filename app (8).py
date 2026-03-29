"""
LinkedIn Job Post Scraper & Extractor
======================================
A Streamlit dashboard that:
1. Takes a natural language search prompt from the user.
2. Converts it to a Google Dork query (site:linkedin.com/posts) via Serper API.
3. Passes each result snippet to Groq LLM to extract structured job data.
4. Displays results in a table and allows Excel export.

Author: Generated for Hi | IIT Mandi MBA (Data Science & AI)
"""

import streamlit as st
import requests
import pandas as pd
import json
import io
import time
from groq import Groq

# ──────────────────────────────────────────────
# PAGE CONFIG
# ──────────────────────────────────────────────
st.set_page_config(
    page_title="LinkedIn Job Scraper",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────────────────────────────────────────
# CUSTOM CSS  (dark, editorial, utilitarian vibe)
# ──────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;600;700&display=swap');

/* Global */
html, body, [class*="css"] {
    font-family: 'IBM Plex Sans', sans-serif;
    background-color: #0d0f14;
    color: #e2e8f0;
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background-color: #131620;
    border-right: 1px solid #1e2433;
}

/* Title block */
.title-block {
    padding: 2rem 0 1rem 0;
    border-bottom: 1px solid #1e2433;
    margin-bottom: 1.5rem;
}
.title-block h1 {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 1.9rem;
    font-weight: 600;
    color: #60a5fa;
    letter-spacing: -0.5px;
    margin: 0;
}
.title-block p {
    color: #64748b;
    font-size: 0.9rem;
    margin-top: 0.4rem;
}

/* Stat cards */
.stat-row {
    display: flex;
    gap: 1rem;
    margin: 1.2rem 0;
}
.stat-card {
    flex: 1;
    background: #131620;
    border: 1px solid #1e2433;
    border-radius: 8px;
    padding: 1rem 1.2rem;
}
.stat-card .label {
    font-size: 0.7rem;
    color: #475569;
    text-transform: uppercase;
    letter-spacing: 1px;
    font-family: 'IBM Plex Mono', monospace;
}
.stat-card .value {
    font-size: 1.8rem;
    font-weight: 700;
    color: #60a5fa;
    font-family: 'IBM Plex Mono', monospace;
    line-height: 1.2;
}

/* Tag pill */
.tag {
    display: inline-block;
    background: #1e2433;
    color: #94a3b8;
    font-size: 0.72rem;
    padding: 2px 8px;
    border-radius: 4px;
    font-family: 'IBM Plex Mono', monospace;
    margin: 2px;
}

/* Snippet card */
.snippet-card {
    background: #131620;
    border: 1px solid #1e2433;
    border-left: 3px solid #3b82f6;
    border-radius: 6px;
    padding: 0.7rem 1rem;
    margin-bottom: 0.5rem;
    font-size: 0.82rem;
    color: #94a3b8;
    font-family: 'IBM Plex Mono', monospace;
}

/* Buttons */
.stButton > button {
    background: #2563eb !important;
    color: white !important;
    border: none !important;
    border-radius: 6px !important;
    font-family: 'IBM Plex Mono', monospace !important;
    font-weight: 600 !important;
    letter-spacing: 0.5px !important;
    padding: 0.5rem 1.5rem !important;
    transition: background 0.2s !important;
}
.stButton > button:hover {
    background: #1d4ed8 !important;
}

/* Inputs */
.stTextInput input, .stTextArea textarea {
    background: #131620 !important;
    border: 1px solid #1e2433 !important;
    color: #e2e8f0 !important;
    border-radius: 6px !important;
    font-family: 'IBM Plex Sans', sans-serif !important;
}

/* Dataframe */
.stDataFrame {
    border: 1px solid #1e2433;
    border-radius: 8px;
    overflow: hidden;
}

/* Expander tweak */
details summary { color: #94a3b8 !important; }
</style>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────
# SIDEBAR — API KEY CONFIG
# ──────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ API Configuration")
    st.caption("Keys are used only in this session and never stored.")

    serper_key = st.text_input(
        "Serper API Key",
        type="password",
        placeholder="sk-serper-xxxxxxxx",
        help="Get your key at https://serper.dev"
    )
    groq_key = st.text_input(
        "Groq API Key",
        type="password",
        placeholder="gsk_xxxxxxxx",
        help="Get your key at https://console.groq.com"
    )

    st.divider()
    st.markdown("### 🔧 Search Settings")
    num_results = st.slider("Number of search results", 5, 20, 10, step=5)
    show_snippets = st.toggle("Show raw snippets", value=False)

    st.divider()
    st.markdown("""
    **How it works**
    1. Your prompt → Google Dork on `site:linkedin.com/posts`
    2. Serper fetches results
    3. Groq LLM extracts structured data per snippet
    4. Results compiled & exported as `.xlsx`
    """)

# ──────────────────────────────────────────────
# HEADER
# ──────────────────────────────────────────────
st.markdown("""
<div class="title-block">
    <h1>🔍 LinkedIn Job Post Scraper</h1>
    <p>Natural language → Google Dork → LLM extraction → Excel export</p>
</div>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────
# HELPER: Build Google Dork query from NL prompt
# ──────────────────────────────────────────────
def build_dork_query(user_prompt: str) -> str:
    """
    Converts a free-form user prompt into a Google Dork query scoped to
    LinkedIn posts. Groq LLM intelligently picks the best keywords and
    dork structure from the user's intent.
    """
    client = Groq(api_key=groq_key)

    system = """You are a Google search dork expert. Given a user's job search intent,
produce a single Google search query that:
- Always starts with: site:linkedin.com/posts
- Includes the most relevant keywords for the job role and requirements
- May include email-related terms like 'email' 'gmail' 'contact' if the user wants contacts
- Keeps the query concise (under 15 words after the site: operator)
- Returns ONLY the raw query string, nothing else."""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        max_tokens=100,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": f"User intent: {user_prompt}"}
        ]
    )
    return response.choices[0].message.content.strip()


# ──────────────────────────────────────────────
# HELPER: Call Serper API
# ──────────────────────────────────────────────
def search_serper(query: str, num: int) -> list[dict]:
    """
    Calls the Serper Google Search API with the given dork query.
    Returns a list of organic result dicts (title, link, snippet).
    """
    url = "https://google.serper.dev/search"
    payload = json.dumps({"q": query, "num": num})
    headers = {
        "X-API-KEY": serper_key,
        "Content-Type": "application/json"
    }
    resp = requests.post(url, headers=headers, data=payload, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    return data.get("organic", [])


# ──────────────────────────────────────────────
# HELPER: LLM extraction from a single snippet
# ──────────────────────────────────────────────
def extract_job_data(snippet: str, title: str, link: str) -> dict | None:
    """
    Sends a snippet + title to Groq LLM with a strict JSON-only prompt.

    The prompt enforces JSON output by:
    1. Specifying the EXACT keys required (email, job_role, location, experience)
    2. Telling the model to return "Not Found" for missing fields — never null or empty
    3. Using "Return ONLY valid JSON" + "No explanation, no markdown" to stop preamble
    4. Low max_tokens to prevent rambling prose before the JSON

    Returns a dict or None if extraction fails / no email found.
    """
    client = Groq(api_key=groq_key)

    # ── THE EXTRACTION PROMPT ──────────────────────────────────────────────
    # Key design decisions:
    # - "Return ONLY valid JSON" + "No explanation, no markdown" stops preamble
    # - Exact key names prevent hallucination of different field names
    # - "Not Found" default ensures every record is complete and consistent
    # - We inject the title so the LLM has more context than just the snippet
    # ──────────────────────────────────────────────────────────────────────
    system_prompt = """You are a data extraction engine. Your ONLY job is to extract job posting information from text.

Return ONLY a valid JSON object with EXACTLY these 4 keys:
{
  "email": "<extracted email address or 'Not Found'>",
  "job_role": "<job title / role being hired for or 'Not Found'>",
  "location": "<city/state/country or 'Remote' or 'Not Found'>",
  "experience": "<experience required e.g. '0-2 years', 'Fresher', '5+ years' or 'Not Found'>"
}

Rules:
- Return NOTHING except the JSON object. No explanation. No markdown. No backticks.
- If a field cannot be determined from the text, use exactly the string: Not Found
- For email: only extract a real email address (contains @ and a domain). Never guess.
- For experience: look for words like 'fresher', 'entry level', '0-1 year', '2-5 years', etc."""

    user_prompt = f"""Post title: {title}
Post URL: {link}
Post snippet: {snippet}

Extract the 4 fields now."""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            max_tokens=200,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )
        raw = response.choices[0].message.content.strip()

        # Strip any accidental markdown fences
        raw = raw.replace("```json", "").replace("```", "").strip()

        extracted = json.loads(raw)

        # Validate required keys exist
        required_keys = {"email", "job_role", "location", "experience"}
        if not required_keys.issubset(extracted.keys()):
            return None

        # Add source metadata
        extracted["source_title"] = title
        extracted["source_url"]   = link
        extracted["snippet"]      = snippet[:200] + "..." if len(snippet) > 200 else snippet

        return extracted

    except (json.JSONDecodeError, KeyError, Exception):
        return None


# ──────────────────────────────────────────────
# MAIN SEARCH FORM
# ──────────────────────────────────────────────
col1, col2 = st.columns([4, 1])
with col1:
    user_prompt = st.text_area(
        "What kind of job posts are you looking for?",
        placeholder='e.g. "Find companies hiring Data Analysts for freshers using gmail in Bangalore"',
        height=90,
        label_visibility="visible"
    )
with col2:
    st.markdown("<br>", unsafe_allow_html=True)
    run_search = st.button("🔍 Search & Extract", use_container_width=True)

# ──────────────────────────────────────────────
# MAIN PIPELINE
# ──────────────────────────────────────────────
if run_search:
    # ── Validation ───────────────────────────
    if not serper_key:
        st.error("⚠️ Please enter your Serper API key in the sidebar.")
        st.stop()
    if not groq_key:
        st.error("⚠️ Please enter your Groq API key in the sidebar.")
        st.stop()
    if not user_prompt.strip():
        st.warning("Please enter a search prompt.")
        st.stop()

    # ── Step 1: Build Dork Query ──────────────
    with st.spinner("🧠 Converting your prompt to a Google Dork query..."):
        try:
            dork_query = build_dork_query(user_prompt.strip())
        except Exception as e:
            st.error(f"Failed to build search query: {e}")
            st.stop()

    st.markdown(f"""
    <div class="snippet-card">
        <span class="tag">GOOGLE DORK</span>&nbsp;
        <strong style="color:#e2e8f0;">{dork_query}</strong>
    </div>
    """, unsafe_allow_html=True)

    # ── Step 2: Serper Search ─────────────────
    with st.spinner(f"📡 Searching LinkedIn posts via Serper ({num_results} results)..."):
        try:
            results = search_serper(dork_query, num_results)
        except requests.exceptions.HTTPError as e:
            st.error(f"Serper API error: {e}")
            st.stop()
        except Exception as e:
            st.error(f"Search failed: {e}")
            st.stop()

    if not results:
        st.warning("No results returned. Try a broader query.")
        st.stop()

    st.success(f"✅ Found **{len(results)}** LinkedIn posts. Running LLM extraction...")

    # Show raw snippets (optional)
    if show_snippets:
        with st.expander(f"📄 Raw Snippets ({len(results)} results)", expanded=False):
            for i, r in enumerate(results, 1):
                st.markdown(f"""
                <div class="snippet-card">
                    <span class="tag">#{i}</span>&nbsp;
                    <strong style="color:#60a5fa;">{r.get('title','')}</strong><br>
                    {r.get('snippet','N/A')}
                </div>
                """, unsafe_allow_html=True)

    # ── Step 3: LLM Extraction ────────────────
    extracted_rows = []
    skipped        = 0
    progress_bar   = st.progress(0, text="Extracting job data from snippets...")

    for i, result in enumerate(results):
        snippet = result.get("snippet", "")
        title   = result.get("title", "")
        link    = result.get("link", "")

        if not snippet:
            skipped += 1
            continue

        row = extract_job_data(snippet, title, link)
        progress_bar.progress((i + 1) / len(results), text=f"Processing result {i+1}/{len(results)}...")

        if row:
            # Only keep rows where an actual email was found
            if row["email"] != "Not Found" and "@" in row["email"]:
                extracted_rows.append(row)

        time.sleep(0.3)  # gentle rate-limit between API calls

    progress_bar.empty()

    # ── Step 4: Display Results ───────────────
    total      = len(results)
    with_email = len(extracted_rows)
    no_email   = total - with_email - skipped

    st.markdown(f"""
    <div class="stat-row">
        <div class="stat-card"><div class="label">Posts Searched</div><div class="value">{total}</div></div>
        <div class="stat-card"><div class="label">Emails Found</div><div class="value" style="color:#34d399">{with_email}</div></div>
        <div class="stat-card"><div class="label">No Email</div><div class="value" style="color:#f87171">{no_email}</div></div>
        <div class="stat-card"><div class="label">Skipped</div><div class="value" style="color:#94a3b8">{skipped}</div></div>
    </div>
    """, unsafe_allow_html=True)

    if not extracted_rows:
        st.warning("No posts with extractable email addresses were found. Try adding 'gmail' or 'email' to your prompt.")
        st.stop()

    # Build DataFrame
    df = pd.DataFrame(extracted_rows)[
        ["email", "job_role", "location", "experience", "source_title", "source_url"]
    ]
    df.columns = ["Email", "Job Role", "Location", "Experience Required", "Post Title", "LinkedIn URL"]

    st.markdown("### 📊 Extracted Job Leads")
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "LinkedIn URL": st.column_config.LinkColumn("LinkedIn URL", display_text="Open →"),
            "Email": st.column_config.TextColumn("Email", width="medium"),
        }
    )

    # ── Step 5: Excel Download ────────────────
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Job Leads")

        # Auto-fit column widths
        worksheet = writer.sheets["Job Leads"]
        for col in worksheet.columns:
            max_len = max(len(str(cell.value or "")) for cell in col)
            worksheet.column_dimensions[col[0].column_letter].width = min(max_len + 4, 60)

    output.seek(0)

    st.download_button(
        label="⬇️ Download as Excel (.xlsx)",
        data=output,
        file_name="linkedin_job_leads.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=False,
    )

    # Save to session state so results persist on rerun
    st.session_state["last_df"]    = df
    st.session_state["last_query"] = dork_query

# ──────────────────────────────────────────────
# RESTORE PREVIOUS SESSION RESULTS
# ──────────────────────────────────────────────
elif "last_df" in st.session_state:
    st.info("📌 Showing results from your last search. Hit **Search & Extract** again to run a new one.")
    st.markdown(f"""
    <div class="snippet-card">
        <span class="tag">LAST DORK</span>&nbsp;
        <strong style="color:#e2e8f0;">{st.session_state['last_query']}</strong>
    </div>
    """, unsafe_allow_html=True)
    st.dataframe(st.session_state["last_df"], use_container_width=True, hide_index=True)

else:
    # Empty state
    st.markdown("""
    <div style="text-align:center; padding: 4rem 2rem; color: #334155;">
        <div style="font-size:3rem; margin-bottom:1rem;">🔎</div>
        <div style="font-family:'IBM Plex Mono',monospace; font-size:1rem; color:#475569;">
            Enter a prompt and click <strong style="color:#60a5fa;">Search & Extract</strong> to begin
        </div>
        <div style="font-size:0.8rem; margin-top:0.8rem; color:#334155;">
            Example: "Find Data Analyst freshers jobs posted on LinkedIn with gmail contact in Delhi"
        </div>
    </div>
    """, unsafe_allow_html=True)
