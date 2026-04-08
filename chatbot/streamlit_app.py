import os
import tempfile
import httpx
import certifi
import streamlit as st

ONECLI_PROXY = os.getenv("ONECLI_PROXY")
ONECLI_URL = os.getenv("ONECLI_URL")
ONECLI_API_KEY = os.getenv("ONECLI_API_KEY")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "FAKE_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "FAKE_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "FAKE_KEY")
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "FAKE_KEY")
RESEND_FROM = os.getenv("RESEND_FROM", "onboarding@resend.dev")

CHAT_MODELS = {
    "OpenAI": {
        "GPT-5.4 mini": "gpt-5.4-mini",
        "GPT-5.4 nano": "gpt-5.4-nano",
    },
    "Anthropic": {
        "Claude Sonnet 4.6": "claude-sonnet-4-6",
        "Claude Haiku 4.5": "claude-haiku-4-5",
    },
    "Google": {
        "Gemini 2.5 Flash": "gemini-2.5-flash",
        "Gemini 2.5 Flash Lite": "gemini-2.5-flash-lite",
    },
}

CA_CERT_FILE = None

def install_onecli_ca():
    global CA_CERT_FILE
    if not ONECLI_URL or not ONECLI_API_KEY:
        return None
    try:
        resp = httpx.get(
            f"{ONECLI_URL}/api/container-config",
            headers={"Authorization": f"Bearer {ONECLI_API_KEY}"},
            timeout=5,
        )
        if resp.status_code == 200:
            ca_pem = resp.json().get("caCertificate")
            if ca_pem:
                with open(certifi.where(), "r") as f:
                    system_cas = f.read()
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pem", mode="w")
                tmp.write(system_cas + "\n" + ca_pem)
                tmp.flush()
                CA_CERT_FILE = tmp.name
    except Exception:
        pass
    return CA_CERT_FILE

if ONECLI_PROXY:
    install_onecli_ca()

def make_httpx_client():
    if ONECLI_PROXY:
        return httpx.Client(proxy=ONECLI_PROXY, verify=CA_CERT_FILE or False)
    return httpx.Client()

st.set_page_config(page_title="OneCLI Demo", page_icon="💬", layout="wide", initial_sidebar_state="auto")

with st.sidebar:
    st.title("💬 OneCLI Chatbot")
    st.caption("Fake API keys, real results. OneCLI injects credentials transparently.")
    mode = st.selectbox("Mode", ["Chat", "Send Email"])
    if mode == "Chat":
        with st.expander("**⚙️ Model Settings**", expanded=True):
            provider = st.selectbox("Provider", list(CHAT_MODELS.keys()))
            model_label = st.selectbox("Model", list(CHAT_MODELS[provider].keys()))
            model = CHAT_MODELS[provider][model_label]
    if ONECLI_PROXY:
        st.success("✅ Routing via OneCLI gateway")
    else:
        st.warning("⚠️ ONECLI_PROXY not set — direct connection")

if mode == "Chat":
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if st.session_state.get("last_provider") != provider:
        st.session_state.messages = []
        st.session_state.last_provider = provider

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("Ask anything"):
        with st.chat_message("user"):
            st.markdown(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})

        with st.chat_message("assistant"):
            try:
                with st.spinner("Please wait..."):
                    http = make_httpx_client()

                    if provider == "OpenAI":
                        from openai import OpenAI
                        client = OpenAI(api_key=OPENAI_API_KEY, http_client=http)
                        response = client.chat.completions.create(
                            model=model,
                            messages=st.session_state.messages,
                        )
                        reply = response.choices[0].message.content

                    elif provider == "Anthropic":
                        import anthropic
                        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY, http_client=http)
                        response = client.messages.create(
                            model=model,
                            max_tokens=1024,
                            messages=st.session_state.messages,
                        )
                        reply = response.content[0].text

                    else:  # Gemini
                        import google.genai as genai
                        if ONECLI_PROXY:
                            os.environ["HTTP_PROXY"] = ONECLI_PROXY
                            os.environ["HTTPS_PROXY"] = ONECLI_PROXY
                        if CA_CERT_FILE:
                            os.environ["SSL_CERT_FILE"] = CA_CERT_FILE
                            os.environ["REQUESTS_CA_BUNDLE"] = CA_CERT_FILE
                        client = genai.Client(api_key=GOOGLE_API_KEY)
                        response = client.models.generate_content(
                            model=model,
                            contents=prompt,
                        )
                        reply = response.text

                    st.markdown(reply)
                    st.session_state.messages.append({"role": "assistant", "content": reply})

            except Exception as e:
                msg = str(e)
                if "401" in msg or "authentication" in msg.lower() or "api_key" in msg.lower() or "invalid x-api-key" in msg.lower():
                    st.error(f"Authentication failed for {provider}. Verify that the API key is set in OneCLI.")
                else:
                    st.error(f"Error: {e}")

else:
    st.subheader("📧 Send Email via Resend")
    st.caption("Fake Resend API key — OneCLI injects the real one.")

    with st.form("email_form"):
        to_email = st.text_input("To", placeholder="recipient@example.com")
        subject = st.text_input("Subject", placeholder="Hello from OneCLI")
        body = st.text_area("Message", placeholder="Type your message here...")
        submitted = st.form_submit_button("Send")

    if submitted:
        if not to_email or not subject or not body:
            st.error("Please fill in all fields.")
        else:
            try:
                with st.spinner("Sending..."):
                    with make_httpx_client() as http:
                        response = http.post(
                            "https://api.resend.com/emails",
                            headers={
                                "Authorization": f"Bearer {RESEND_API_KEY}",
                                "Content-Type": "application/json",
                            },
                            json={
                                "from": RESEND_FROM,
                                "to": [to_email],
                                "subject": subject,
                                "text": body,
                            },
                        )
                    if response.status_code in (200, 201):
                        st.success(f"Email sent! ID: {response.json().get('id')}")
                    else:
                        st.error(f"Failed: {response.status_code} — {response.text}")
            except Exception as e:
                st.error(f"Error: {e}")
