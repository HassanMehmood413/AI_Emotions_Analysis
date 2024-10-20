import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
import joblib
import requests
from bs4 import BeautifulSoup
from googleapiclient.discovery import build
from together import Together
import os
import time
from gtts import gTTS
import tempfile
from langdetect import detect
import sounddevice as sd
import numpy as np
from pydub import AudioSegment
from openai import OpenAI
from streamlit_mic_recorder import speech_to_text
from cerebras.cloud.sdk import Cerebras
from streamlit_TTS import auto_play, text_to_speech, text_to_audio


# API Keys
TOGETHER_API_KEY = 'a5b0cf3c0359bb15a8ae6bb92f1e63d52af5012ae6eedb646539753b28733e89'
GOOGLE_API_KEY = 'AIzaSyB3oeVUJrw-BY0fpxVkx191cL8HLnbKbbk'
GOOGLE_CX = 'a76d5546fd9214b49'
OPENAI_API_KEY = '93ab3fc4ff08425886d88fa0127dcb3f'
CEREBRAS_API_KEY =  "csk-emxwh6neyvmt62vhm89c34cwt9f939v2nvy3xfeekpvtr52w"

# Set Together API key
os.environ["TOGETHER_API_KEY"] = TOGETHER_API_KEY

# Initialize Together AI client
together_client = Together(api_key=TOGETHER_API_KEY)
if not CEREBRAS_API_KEY: 
    CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY")
# Initialize OpenAI client
client = OpenAI(
    api_key=OPENAI_API_KEY,
    base_url="https://api.aimlapi.com",
)

cerebras_client = Cerebras(
    api_key=CEREBRAS_API_KEY
)
# Load emotion detection model
pipe_lr = joblib.load(open("model/text_emotion.pkl", "rb"))

# Emojis for different emotions
emotions_emoji_dict = {
    "anger": "😠", "disgust": "🤮", "fear": "😨😱", 
    "happy": "🤗", "joy": "😂", "neutral": "😐", 
    "sad": "😔", "sadness": "😔", "shame": "😳", 
    "surprise": "😮"
}

# Functions for emotion detection
def predict_emotions(docx):
    results = pipe_lr.predict([docx])
    return results[0]

def get_prediction_proba(docx):
    results = pipe_lr.predict_proba([docx])
    return results

def ai_analysis(text, predicted_emotion):
    try:
        prompt = f"You are an AI assistant that provides detailed emotional analysis based on user input. The user text reflects a tone of '{predicted_emotion}'. " \
                 "Please offer a thoughtful analysis of the emotions, considering the detected tone, and give suggestions on how the user might feel or act next."

        response = together_client.chat.completions.create(
            model="meta-llama/Llama-3.2-11B-Vision-Instruct-Turbo",
            messages=[{"role": "system", "content": "You are an AI assistant analyzing emotional tone."},
                      {"role": "user", "content": prompt},
                      {"role": "user", "content": text}],
            max_tokens=500,
            temperature=0.7,
            top_p=0.7,
            top_k=50,
            repetition_penalty=1,
            stop=["<|eot_id|>", "<|eom_id|>"],
            stream=True
        )

        full_response = ""
        for token in response:
            if hasattr(token, 'choices') and token.choices:
                content = token.choices[0].delta.content
                full_response += content

        return full_response or "No analysis content returned."
    except Exception as e:
        print(f"Error in AI analysis: {str(e)}")
        try: 
            response = cerebras_client.chat.completions.create(model="llama3.1-70b",
                    messages=[{"role": "system", "content": "You are an AI assistant analyzing emotional tone."},
                      {"role": "user", "content": prompt},
                      {"role": "user", "content": text}],)
            return response.choices[0].message.content
        except Exception as e:
            print(f"Error in AI analysis: {str(e)}")
            return "Could not complete the analysis due to an error."

def get_emotion(analysis, user_query):
    emotion_color_map = {
       "calm": "#005073",  # Dark blue for calmness
        "trust": "#005073",  # Dark blue for trust
        "serenity": "#0073e6",  # Bright blue for serenity
        "balance": "#73a942",  # Green for balance
        "harmony": "#73a942",  # Green for harmony
        "nature": "#73a942",  # Green for nature
        "soothe": "#a64ca6",  # Purple for soothing
        "relaxation": "#a64ca6",  # Purple for relaxation
        "care": "#ff6f61",  # Soft red for care
        "compassion": "#ff6f61",  # Soft red for compassion
        "warmth": "#ff6f61",  # Soft red for warmth
        "simplicity": "#8c8c8c",  # Grey for simplicity
        "depressed": "#005073",  # Dark blue for depression
        "default": "#005073"  # Default color is dark blue
    }
    

    # Determine the color based on the emotion
    emotion_extraction_prompt = f"from above conversation history you have to extract teh emotion of user you have to give output as one of the {emotion_color_map.keys()} don't write any additional text and any code. given assistant repsonse:{analysis} user_query: {user_query}"


    emotion = cerebras_client.chat.completions.create(model="llama3.1-8b", messages = [{"role": "user", "content": emotion_extraction_prompt}])
    emotion = emotion.choices[0].message.content
    color = emotion_color_map.get(emotion, emotion_color_map["default"])
    # Display the assistant message in the determined color

    analysis_paragraphs = analysis.split('\n')
    for paragraph in analysis_paragraphs:
        st.markdown(f"<p style='color: {color};'>{paragraph}</p>", unsafe_allow_html=True)

    return emotion 
# Function for Google Custom Search API
def google_search(query):
    service = build("customsearch", "v1", developerKey=GOOGLE_API_KEY)
    result = service.cse().list(q=query, cx=GOOGLE_CX).execute()
    return result.get('items', [])

# Scraping article content from a URL
def extract_article_content(url):
    try:
        response = requests.get(url)
        soup = BeautifulSoup(response.content, 'html.parser')
        paragraphs = soup.find_all('p')
        text = " ".join([para.get_text() for para in paragraphs])
        return text
    except Exception as e:
        print(f"Error extracting article content: {e}")
        return None

# # Convert text to audio
# def text_to_audio(text, lang='en'):
#     tts = gTTS(text=text, lang=lang)
#     with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
#         audio_file_path = fp.name
#         tts.save(audio_file_path)
#     return audio_file_path

# Play audio using sounddevice
def play_audio(file_path):
    audio_segment = AudioSegment.from_mp3(file_path)
    samples = np.array(audio_segment.get_array_of_samples())
    if audio_segment.channels == 2:
        samples = samples.reshape((-1, 2))
    sd.play(samples, samplerate=audio_segment.frame_rate)
    sd.wait()

# Detect language
def detect_language(text):
    return detect(text)

def callback():
    if st.session_state.my_stt_output:
        st.write(st.session_state.my_stt_output)

# Main App
def main():
    st.set_page_config(page_title="Emotion Detection App", layout="wide")
    st.title("🧠 Advanced Text Emotion Detection & Summarization App")
    st.write("### Detect emotions in text, emails, and articles.")
    
    theme = st.sidebar.selectbox("Select Theme", ["Light", "Dark"])
    if theme == "Dark":
        st.markdown("""<style>
            .stApp {
                background-color: #121212;
                color: white;
            }
            .stSidebar {
                background-color: #1e1e1e;
                color: white;
            }
            </style>""", unsafe_allow_html=True)

    option = st.sidebar.selectbox("Choose input type", ["Audio Input", "Text Input", "Email Input", "Article URL", "Google Search"])

    st.sidebar.write("### Instructions")
    st.sidebar.write("""\
    1. **Text Input**: Type or paste any text you want to analyze for emotional tone.
    2. **Email Input**: Paste the content of your email to understand its emotional context.
    3. **Article URL**: Provide a URL of an article, and the app will extract and analyze its emotional tone.
    4. **Google Search**: Enter a search query to find articles and analyze their emotional content.
    5. **Audio Input**: Speak your text, and the app will analyze the emotions in your spoken words.
    """)
    st.sidebar.write("---")

    st.sidebar.write("### Find the source code here:")
    st.sidebar.markdown("[GitHub Repository](https://github.com/yourusername/your-repo-name)")

    if option == "Text Input":
        st.subheader("💬 Emotion Detection from Text")
        raw_text = st.text_area("Type your text here:", height=150)
        if st.button("Analyze Text Emotions"):
            with st.spinner("Analyzing..."):
                if raw_text:
                    prediction = predict_emotions(raw_text)
                    probability = get_prediction_proba(raw_text)
                    st.success(f"**Predicted Emotion:** {prediction} {emotions_emoji_dict[prediction]}")
                    st.write(f"**Prediction Confidence:** {np.max(probability):.2f}")

                    proba_df = pd.DataFrame(probability, columns=pipe_lr.classes_)
                    proba_df_clean = proba_df.T.reset_index()
                    proba_df_clean.columns = ["emotions", "probability"]
                    fig = alt.Chart(proba_df_clean).mark_bar().encode(
                        x='emotions',
                        y='probability',
                        color='emotions'
                    ).properties(title="Emotion Probabilities")
                    st.altair_chart(fig, use_container_width=True)

                    analysis = ai_analysis(raw_text, prediction)
                    st.write("### AI Analysis:")
                    st.markdown(f'<div style="color:black;">{analysis}</div>', unsafe_allow_html=True)

                    audio_file = text_to_audio(analysis)
                    auto_play(audio_file)

                    user_response = st.text_input("🤔 How do you feel about this analysis? What would you like to discuss?", "")
                    if user_response:
                        empathetic_response = ai_analysis(user_response, prediction)
                        st.write("### AI Empathetic Response:")
                        st.markdown(f'<div style="color:black;">{empathetic_response}</div>', unsafe_allow_html=True)

                    st.download_button(
                        "📥 Download Results as CSV", 
                        proba_df_clean.to_csv(index=False), 
                        "emotion_probabilities.csv", 
                        "text/csv"
                    )

    elif option == "Email Input":
        st.subheader("📧 Emotion Detection from Email")
        email_text = st.text_area("Paste your email content here:", height=150)
        if st.button("Analyze Email Emotions"):
            with st.spinner("Analyzing..."):
                if email_text:
                    prediction = predict_emotions(email_text)
                    probability = get_prediction_proba(email_text)
                    st.success(f"**Predicted Emotion:** {prediction} {emotions_emoji_dict[prediction]}")
                    st.write(f"**Prediction Confidence:** {np.max(probability):.2f}")

                    proba_df = pd.DataFrame(probability, columns=pipe_lr.classes_)
                    proba_df_clean = proba_df.T.reset_index()
                    proba_df_clean.columns = ["emotions", "probability"]
                    fig = alt.Chart(proba_df_clean).mark_bar().encode(
                        x='emotions',
                        y='probability',
                        color='emotions'
                    ).properties(title="Emotion Probabilities")
                    st.altair_chart(fig, use_container_width=True)

                    analysis = ai_analysis(email_text, prediction)
                    st.write("### AI Analysis:")
                    st.markdown(f'<div style="color:black;">{analysis}</div>', unsafe_allow_html=True)

                    audio_file = text_to_audio(analysis)
                    auto_play(audio_file)

                    user_response = st.text_input("🤔 How do you feel about this analysis? What would you like to discuss?", "")
                    if user_response:
                        empathetic_response = ai_analysis(user_response, prediction)
                        st.write("### AI Empathetic Response:")
                        st.markdown(f'<div style="color:black;">{empathetic_response}</div>', unsafe_allow_html=True)

    elif option == "Article URL":
        st.subheader("📄 Emotion Detection from Article URL")
        article_url = st.text_input("Enter the URL of the article:")
        if st.button("Extract and Analyze Article"):
            with st.spinner("Extracting article content..."):
                article_content = extract_article_content(article_url)
                if article_content:
                    prediction = predict_emotions(article_content)
                    probability = get_prediction_proba(article_content)
                    st.success(f"**Predicted Emotion:** {prediction} {emotions_emoji_dict[prediction]}")
                    st.write(f"**Prediction Confidence:** {np.max(probability):.2f}")

                    proba_df = pd.DataFrame(probability, columns=pipe_lr.classes_)
                    proba_df_clean = proba_df.T.reset_index()
                    proba_df_clean.columns = ["emotions", "probability"]
                    fig = alt.Chart(proba_df_clean).mark_bar().encode(
                        x='emotions',
                        y='probability',
                        color='emotions'
                    ).properties(title="Emotion Probabilities")
                    st.altair_chart(fig, use_container_width=True)

                    analysis = ai_analysis(article_content, prediction)
                    st.write("### AI Analysis:")
                    st.markdown(f'<div style="color:black;">{analysis}</div>', unsafe_allow_html=True)

                    audio_file = text_to_audio(analysis)
                    auto_play(audio_file)

                    user_response = st.text_input("🤔 How do you feel about this analysis? What would you like to discuss?", "")
                    if user_response:
                        empathetic_response = ai_analysis(user_response, prediction)
                        st.write("### AI Empathetic Response:")
                        st.markdown(f'<div style="color:black;">{empathetic_response}</div>', unsafe_allow_html=True)

    elif option == "Google Search":
        st.subheader("🔍 Google Search for Emotion Detection")
        search_query = st.text_input("Enter your search query:")
        if st.button("Search"):
            with st.spinner("Searching..."):
                results = google_search(search_query)
                if results:
                    for result in results:
                        st.write(f"[{result['title']}]({result['link']})")
                        st.write(result['snippet'])
                        st.write("---")
                else:
                    st.write("No results found.")

    elif option == "Audio Input":
        st.subheader("🎤 Emotion Detection from Audio Input")
        audio_input = speech_to_text(key='my_stt', callback=callback)
        
        if st.button("Analyze Audio"):
            if audio_input:
                st.session_state.last_input_time = time.time()
                with st.spinner("Analyzing..."):
                    prediction = predict_emotions(audio_input)
                    probability = get_prediction_proba(audio_input)
                    st.success(f"**Predicted Emotion:** {prediction} {emotions_emoji_dict[prediction]}")
                    st.write(f"**Prediction Confidence:** {np.max(probability):.2f}")

                    proba_df = pd.DataFrame(probability, columns=pipe_lr.classes_)
                    proba_df_clean = proba_df.T.reset_index()
                    proba_df_clean.columns = ["emotions", "probability"]
                    fig = alt.Chart(proba_df_clean).mark_bar().encode(
                        x='emotions',
                        y='probability',
                        color='emotions'
                    ).properties(title="Emotion Probabilities")
                    st.altair_chart(fig, use_container_width=True)

                    analysis = ai_analysis(audio_input, prediction)
                    st.write("### AI Analysis:")
                    st.markdown(f'<div style="color:black;">{analysis}</div>', unsafe_allow_html=True)

                    audio_file = text_to_audio(analysis)
                    auto_play(audio_file)

                    user_response = st.text_input("🤔 How do you feel about this analysis? What would you like to discuss?", "")
                    if user_response:
                        empathetic_response = ai_analysis(user_response, prediction)
                        st.write("### AI Empathetic Response:")
                        st.markdown(f'<div style="color:black;">{empathetic_response}</div>', unsafe_allow_html=True)


if __name__ == "__main__":
    main()








# import streamlit as st
# import pandas as pd
# import numpy as np
# import altair as alt
# import joblib
# import requests
# from bs4 import BeautifulSoup
# from googleapiclient.discovery import build
# from together import Together
# import os
# import time
# from gtts import gTTS
# import tempfile
# from langdetect import detect
# import sounddevice as sd
# import numpy as np
# from pydub import AudioSegment
# from openai import OpenAI
# from streamlit_mic_recorder import speech_to_text
# from cerebras.cloud.sdk import Cerebras
# from streamlit_TTS import auto_play, text_to_speech, text_to_audio


# # API Keys
# TOGETHER_API_KEY = st.secrets["Together_API"]
# GOOGLE_API_KEY = st.secrets["Google_API"]
# GOOGLE_CX = st.secrets["Google_CX"]
# OPENAI_API_KEY = st.secrets["Open_API"]
# CEREBRAS_API_KEY = st.secrets["CEREBRAS_API_KEY"]
# # Set Together API key
# os.environ["TOGETHER_API_KEY"] = TOGETHER_API_KEY

# # Initialize Together AI client
# together_client = Together(api_key=TOGETHER_API_KEY)
# if not CEREBRAS_API_KEY: 
#     CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY")
# # Initialize OpenAI client
# client = OpenAI(
#     api_key=OPENAI_API_KEY,
#     base_url="https://api.aimlapi.com",
# )

# cerebras_client = Cerebras(
#     api_key=CEREBRAS_API_KEY
# )
# # Load emotion detection model
# pipe_lr = joblib.load(open("model/text_emotion.pkl", "rb"))

# # Emojis for different emotions
# emotions_emoji_dict = {
#     "anger": "😠", "disgust": "🤮", "fear": "😨😱", 
#     "happy": "🤗", "joy": "😂", "neutral": "😐", 
#     "sad": "😔", "sadness": "😔", "shame": "😳", 
#     "surprise": "😮"
# }

# # Functions for emotion detection
# def predict_emotions(docx):
#     results = pipe_lr.predict([docx])
#     return results[0]

# def get_prediction_proba(docx):
#     results = pipe_lr.predict_proba([docx])
#     return results

# def ai_analysis(text, predicted_emotion):
#     try:
#         prompt = f"You are an AI assistant that provides detailed emotional analysis based on user input. The user text reflects a tone of '{predicted_emotion}'. " \
#                  "Please offer a thoughtful analysis of the emotions, considering the detected tone, and give suggestions on how the user might feel or act next."

#         response = together_client.chat.completions.create(
#             model="meta-llama/Llama-3.2-11B-Vision-Instruct-Turbo",
#             messages=[{"role": "system", "content": "You are an AI assistant analyzing emotional tone."},
#                       {"role": "user", "content": prompt},
#                       {"role": "user", "content": text}],
#             max_tokens=500,
#             temperature=0.7,
#             top_p=0.7,
#             top_k=50,
#             repetition_penalty=1,
#             stop=["<|eot_id|>", "<|eom_id|>"],
#             stream=True
#         )

#         full_response = ""
#         for token in response:
#             if hasattr(token, 'choices') and token.choices:
#                 content = token.choices[0].delta.content
#                 full_response += content

#         return full_response or "No analysis content returned."
#     except Exception as e:
#         print(f"Error in AI analysis: {str(e)}")
#         try: 
#             response = cerebras_client.chat.completions.create(model="llama3.1-70b",
#                     messages=[{"role": "system", "content": "You are an AI assistant analyzing emotional tone."},
#                       {"role": "user", "content": prompt},
#                       {"role": "user", "content": text}],)
#             return response.choices[0].message.content
#         except Exception as e:
#             print(f"Error in AI analysis: {str(e)}")
#             return "Could not complete the analysis due to an error."

# def get_emotion(analysis, user_query):
#     emotion_color_map = {
#         "calm": "#A7C7E7",
#         "trust": "#A7C7E7",
#         "serenity": "#A7C7E7",
#         "balance": "#C8E6C9",
#         "harmony": "#C8E6C9",
#         "nature": "#C8E6C9",
#         "soothe": "#E1BEE7",
#         "relaxation": "#E1BEE7",
#         "care": "#F8BBD0",
#         "compassion": "#F8BBD0",
#         "warmth": "#F8BBD0",
#         "simplicity": "#D7CCC8",
#         "depressed": "#A7C7E7",  # Blue for depression
#         "default": "#A7C7E7"  # Default color is blue
#     }
    

#     # Determine the color based on the emotion
#     emotion_extraction_prompt = f"from above conversation history you have to extract teh emotion of user you have to give output as one of the {emotion_color_map.keys()} don't write any additional text and any code. given assistant repsonse:{analysis} user_query: {user_query}"


#     emotion = cerebras_client.chat.completions.create(model="llama3.1-8b", messages = [{"role": "user", "content": emotion_extraction_prompt}])
#     emotion = emotion.choices[0].message.content
#     color = emotion_color_map.get(emotion, emotion_color_map["default"])
#     # Display the assistant message in the determined color

#     analysis_paragraphs = analysis.split('\n')
#     for paragraph in analysis_paragraphs:
#         st.markdown(f"<p style='color: {color};'>{paragraph}</p>", unsafe_allow_html=True)

#     return emotion 
# # Function for Google Custom Search API
# def google_search(query):
#     service = build("customsearch", "v1", developerKey=GOOGLE_API_KEY)
#     result = service.cse().list(q=query, cx=GOOGLE_CX).execute()
#     return result.get('items', [])

# # Scraping article content from a URL
# def extract_article_content(url):
#     try:
#         response = requests.get(url)
#         soup = BeautifulSoup(response.content, 'html.parser')
#         paragraphs = soup.find_all('p')
#         text = " ".join([para.get_text() for para in paragraphs])
#         return text
#     except Exception as e:
#         print(f"Error extracting article content: {e}")
#         return None

# # # Convert text to audio
# # def text_to_audio(text, lang='en'):
# #     tts = gTTS(text=text, lang=lang)
# #     with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
# #         audio_file_path = fp.name
# #         tts.save(audio_file_path)
# #     return audio_file_path

# # Play audio using sounddevice
# def play_audio(file_path):
#     audio_segment = AudioSegment.from_mp3(file_path)
#     samples = np.array(audio_segment.get_array_of_samples())
#     if audio_segment.channels == 2:
#         samples = samples.reshape((-1, 2))
#     sd.play(samples, samplerate=audio_segment.frame_rate)
#     sd.wait()

# # Detect language
# def detect_language(text):
#     return detect(text)

# def callback():
#     if st.session_state.my_stt_output:
#         st.write(st.session_state.my_stt_output)

# # Main App
# def main():
#     st.set_page_config(page_title="Emotion Detection App", layout="wide")
#     st.title("🧠 Advanced Text Emotion Detection & Summarization App")
#     st.write("### Detect emotions in text, emails, and articles.")
    
#     theme = st.sidebar.selectbox("Select Theme", ["Light", "Dark"])
#     if theme == "Dark":
#         st.markdown("""<style>
#             .stApp {
#                 background-color: #121212;
#                 color: white;
#             }
#             .stSidebar {
#                 background-color: #1e1e1e;
#                 color: white;
#             }
#             </style>""", unsafe_allow_html=True)

#     option = st.sidebar.selectbox("Choose input type", ["Audio Input", "Text Input", "Email Input", "Article URL", "Google Search"])

#     st.sidebar.write("### Instructions")
#     st.sidebar.write("""\
#     1. **Text Input**: Type or paste any text you want to analyze for emotional tone.
#     2. **Email Input**: Paste the content of your email to understand its emotional context.
#     3. **Article URL**: Provide a URL of an article, and the app will extract and analyze its emotional tone.
#     4. **Google Search**: Enter a search query to find articles and analyze their emotional content.
#     5. **Audio Input**: Speak your text, and the app will analyze the emotions in your spoken words.
#     """)
#     st.sidebar.write("---")

#     st.sidebar.write("### Find the source code here:")
#     st.sidebar.markdown("[GitHub Repository](https://github.com/yourusername/your-repo-name)")

#     if option == "Text Input":
#         st.subheader("💬 Emotion Detection from Text")
#         raw_text = st.text_area("Type your text here:", height=150)
#         if st.button("Analyze Text Emotions"):
#             with st.spinner("Analyzing..."):
#                 if raw_text:
#                     prediction = predict_emotions(raw_text)
#                     probability = get_prediction_proba(raw_text)
#                     st.success(f"**Predicted Emotion:** {prediction} {emotions_emoji_dict[prediction]}")
#                     st.write(f"**Prediction Confidence:** {np.max(probability):.2f}")

#                     proba_df = pd.DataFrame(probability, columns=pipe_lr.classes_)
#                     proba_df_clean = proba_df.T.reset_index()
#                     proba_df_clean.columns = ["emotions", "probability"]
#                     fig = alt.Chart(proba_df_clean).mark_bar().encode(
#                         x='emotions',
#                         y='probability',
#                         color='emotions'
#                     ).properties(title="Emotion Probabilities")
#                     st.altair_chart(fig, use_container_width=True)

#                     analysis = ai_analysis(raw_text, prediction)
#                     st.write("### AI Analysis:")
#                     st.markdown(f'<div style="color:black;">{analysis}</div>', unsafe_allow_html=True)

#                     audio_file = text_to_audio(analysis)
#                     auto_play(audio_file)

#                     user_response = st.text_input("🤔 How do you feel about this analysis? What would you like to discuss?", "")
#                     if user_response:
#                         empathetic_response = ai_analysis(user_response, prediction)
#                         st.write("### AI Empathetic Response:")
#                         st.markdown(f'<div style="color:black;">{empathetic_response}</div>', unsafe_allow_html=True)

#                     st.download_button(
#                         "📥 Download Results as CSV", 
#                         proba_df_clean.to_csv(index=False), 
#                         "emotion_probabilities.csv", 
#                         "text/csv"
#                     )

#     elif option == "Email Input":
#         st.subheader("📧 Emotion Detection from Email")
#         email_text = st.text_area("Paste your email content here:", height=150)
#         if st.button("Analyze Email Emotions"):
#             with st.spinner("Analyzing..."):
#                 if email_text:
#                     prediction = predict_emotions(email_text)
#                     probability = get_prediction_proba(email_text)
#                     st.success(f"**Predicted Emotion:** {prediction} {emotions_emoji_dict[prediction]}")
#                     st.write(f"**Prediction Confidence:** {np.max(probability):.2f}")

#                     proba_df = pd.DataFrame(probability, columns=pipe_lr.classes_)
#                     proba_df_clean = proba_df.T.reset_index()
#                     proba_df_clean.columns = ["emotions", "probability"]
#                     fig = alt.Chart(proba_df_clean).mark_bar().encode(
#                         x='emotions',
#                         y='probability',
#                         color='emotions'
#                     ).properties(title="Emotion Probabilities")
#                     st.altair_chart(fig, use_container_width=True)

#                     analysis = ai_analysis(email_text, prediction)
#                     st.write("### AI Analysis:")
#                     st.markdown(f'<div style="color:black;">{analysis}</div>', unsafe_allow_html=True)

#                     audio_file = text_to_audio(analysis)
#                     auto_play(audio_file)

#                     user_response = st.text_input("🤔 How do you feel about this analysis? What would you like to discuss?", "")
#                     if user_response:
#                         empathetic_response = ai_analysis(user_response, prediction)
#                         st.write("### AI Empathetic Response:")
#                         st.markdown(f'<div style="color:black;">{empathetic_response}</div>', unsafe_allow_html=True)

#     elif option == "Article URL":
#         st.subheader("📄 Emotion Detection from Article URL")
#         article_url = st.text_input("Enter the URL of the article:")
#         if st.button("Extract and Analyze Article"):
#             with st.spinner("Extracting article content..."):
#                 article_content = extract_article_content(article_url)
#                 if article_content:
#                     prediction = predict_emotions(article_content)
#                     probability = get_prediction_proba(article_content)
#                     st.success(f"**Predicted Emotion:** {prediction} {emotions_emoji_dict[prediction]}")
#                     st.write(f"**Prediction Confidence:** {np.max(probability):.2f}")

#                     proba_df = pd.DataFrame(probability, columns=pipe_lr.classes_)
#                     proba_df_clean = proba_df.T.reset_index()
#                     proba_df_clean.columns = ["emotions", "probability"]
#                     fig = alt.Chart(proba_df_clean).mark_bar().encode(
#                         x='emotions',
#                         y='probability',
#                         color='emotions'
#                     ).properties(title="Emotion Probabilities")
#                     st.altair_chart(fig, use_container_width=True)

#                     analysis = ai_analysis(article_content, prediction)
#                     st.write("### AI Analysis:")
#                     st.markdown(f'<div style="color:black;">{analysis}</div>', unsafe_allow_html=True)

#                     audio_file = text_to_audio(analysis)
#                     auto_play(audio_file)

#                     user_response = st.text_input("🤔 How do you feel about this analysis? What would you like to discuss?", "")
#                     if user_response:
#                         empathetic_response = ai_analysis(user_response, prediction)
#                         st.write("### AI Empathetic Response:")
#                         st.markdown(f'<div style="color:black;">{empathetic_response}</div>', unsafe_allow_html=True)

#     elif option == "Google Search":
#         st.subheader("🔍 Google Search for Emotion Detection")
#         search_query = st.text_input("Enter your search query:")
#         if st.button("Search"):
#             with st.spinner("Searching..."):
#                 results = google_search(search_query)
#                 if results:
#                     for result in results:
#                         st.write(f"[{result['title']}]({result['link']})")
#                         st.write(result['snippet'])
#                         st.write("---")
#                 else:
#                     st.write("No results found.")

#     elif option == "Audio Input":
#         st.subheader("🎤 Emotion Detection from Audio Input")
#         audio_input = speech_to_text(key='my_stt', callback=callback)
        
#         if st.button("Analyze Audio"):
#             if audio_input:
#                 st.session_state.last_input_time = time.time()
#                 with st.spinner("Analyzing..."):
#                     prediction = predict_emotions(audio_input)
#                     probability = get_prediction_proba(audio_input)
#                     st.success(f"**Predicted Emotion:** {prediction} {emotions_emoji_dict[prediction]}")
#                     st.write(f"**Prediction Confidence:** {np.max(probability):.2f}")

#                     proba_df = pd.DataFrame(probability, columns=pipe_lr.classes_)
#                     proba_df_clean = proba_df.T.reset_index()
#                     proba_df_clean.columns = ["emotions", "probability"]
#                     fig = alt.Chart(proba_df_clean).mark_bar().encode(
#                         x='emotions',
#                         y='probability',
#                         color='emotions'
#                     ).properties(title="Emotion Probabilities")
#                     st.altair_chart(fig, use_container_width=True)

#                     analysis = ai_analysis(audio_input, prediction)
#                     st.write("### AI Analysis:")
#                     st.markdown(f'<div style="color:black;">{analysis}</div>', unsafe_allow_html=True)

#                     audio_file = text_to_audio(analysis)
#                     auto_play(audio_file)

#                     user_response = st.text_input("🤔 How do you feel about this analysis? What would you like to discuss?", "")
#                     if user_response:
#                         empathetic_response = ai_analysis(user_response, prediction)
#                         st.write("### AI Empathetic Response:")
#                         st.markdown(f'<div style="color:black;">{empathetic_response}</div>', unsafe_allow_html=True)


# if __name__ == "__main__":
#     main()
