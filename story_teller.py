import streamlit as st
import os
import google.generativeai as genai
from gtts import gTTS
import requests
import io
from PIL import Image

# --- Configuration & AI Setup ---

gemini_api_key = "AIzaSyBHoUFd_2umSWmvDSwmNW_r5J_NAeyXt6s"
HF_API_TOKEN = "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"


# Configure the clients
genai.configure(api_key=gemini_api_key)
text_model = genai.GenerativeModel(model_name="gemini-1.5-flash-latest")
IMAGE_API_URL = "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-xl-base-1.0"

# --- Core Functions ---

def generate_image(prompt: str, filename="scene.png"):
    """Generates an image using Hugging Face's Inference API."""
    headers = {"Authorization": f"Bearer {HF_API_TOKEN}"}
    image_prompt = f"Digital art style, cinematic lighting, fantasy, a scene from an interactive story: {prompt}"
    try:
        response = requests.post(IMAGE_API_URL, headers=headers, json={"inputs": image_prompt})
        response.raise_for_status()
        image = Image.open(io.BytesIO(response.content))
        image.save(filename)
        return filename
    except Exception as e:
        print(f"Hugging Face image generation failed: {e}")
        return None

def parse_story_and_choices(llm_output: str):
    """Parses the LLM's output for the narrative and choices."""
    try:
        choices_start_index = llm_output.lower().index("choice 1:")
        narrative = llm_output[:choices_start_index].strip()
        choices_text = llm_output[choices_start_index:]
        choices_list = [line.split(":", 1)[1].strip() for line in choices_text.splitlines() if line.strip()]
        return narrative, choices_list
    except ValueError:
        return llm_output.strip(), []

def generate_story_turn(story_history: str, user_choice: str, memory: list) -> str:
    """Generates just the story and choices."""
    system_prompt = (
        "You are a master storyteller creating an interactive adventure. Your goal is to guide the story to a satisfying conclusion within 5-10 turns. "
        "Continue the story based on the user's last choice, keeping the established facts from the 'KEY MEMORIES' section in mind. "
        "When you feel a natural ending point has been reached, one of your choices must be: 'Bring the story to a conclusion.'\n"
        "End your response with three new, distinct choices for the user, formatted exactly like this:\n"
        "CHOICE 1: [First choice text]\n"
        "CHOICE 2: [Second choice text]\n"
        "CHOICE 3: [Third choice text]"
    )
    memory_str = "\n".join(f"- {fact}" for fact in memory)
    full_prompt = f"{system_prompt}\n\n--- STORY SO FAR ---\n{story_history}\n\n--- KEY MEMORIES ---\n{memory_str}\n\n--- USER'S CHOICE ---\n{user_choice}\n\n--- WHAT HAPPENS NEXT? ---"
    try:
        response = text_model.generate_content(full_prompt)
        return response.text if response.text else "The story fades..."
    except Exception as e:
        print(f"Gemini error: {e}")
        return "The storyteller seems to have lost their train of thought."

def generate_memory_updates(narrative_segment: str) -> list:
    """Takes a piece of narrative and extracts key facts to remember."""
    if not narrative_segment: return []
    prompt = f"Analyze the following story segment and extract a list of new, important facts to remember (key characters, items, locations, or plot points). List each fact on a new line.\n\n--- STORY SEGMENT ---\n{narrative_segment}\n\n--- NEW FACTS ---"
    try:
        response = text_model.generate_content(prompt)
        return [line.strip() for line in response.text.splitlines() if line.strip()]
    except Exception as e:
        print(f"Memory generation error: {e}")
        return []

def generate_audio(text, filename="narration.mp3"):
    """Converts text to an MP3 file using gTTS."""
    if not text: return None
    try:
        tts = gTTS(text=text, lang='en')
        tts.save(filename)
        return filename
    except Exception as e:
        print(f"gTTS audio generation failed: {e}")
        return None

# --- Streamlit App UI and Logic ---

st.set_page_config(page_title="Project GENESIS", layout="wide", page_icon="📖")

if 'game_started' not in st.session_state:
    st.session_state.game_started = False
    st.session_state.story_history = ""
    st.session_state.memory_list = []
    st.session_state.choices = []
    st.session_state.narration_file = None
    st.session_state.image_file = None
    st.session_state.game_over = False

st.title("📖 Project GENESIS: An Interactive AI Storyteller")

if not st.session_state.game_started:
    st.subheader("Begin your adventure...")
    prompt = st.text_input("Enter your initial story prompt:", placeholder="e.g., A knight on a quest to find a mythical dragon...", label_visibility="collapsed")
    
    if st.button("Start Story", type="primary"):
        if prompt:
            with st.spinner("Your story is beginning..."):
                story_response = generate_story_turn("", prompt, [])
                initial_narrative, initial_choices = parse_story_and_choices(story_response)

                st.session_state.memory_list = generate_memory_updates(initial_narrative)
                st.session_state.narration_file = generate_audio(initial_narrative)
                st.session_state.image_file = generate_image(initial_narrative)

                st.session_state.story_history = initial_narrative
                st.session_state.choices = initial_choices
                st.session_state.game_started = True
                st.rerun()
        else:
            st.warning("Please enter a prompt to start your story.")

else:
    sidebar, main_content = st.columns([1, 2])

    with sidebar:
        st.header("Scene")
        if st.session_state.image_file and os.path.exists(st.session_state.image_file):
            # FIX: Removed use_column_width=True to prevent warnings
            st.image(st.session_state.image_file)
        
        st.header("Narration")
        if st.session_state.narration_file and os.path.exists(st.session_state.narration_file):
            st.audio(st.session_state.narration_file)

        with st.expander("Show AI Memory"):
            if st.session_state.memory_list:
                for fact in st.session_state.memory_list:
                    st.markdown(f"- {fact}")
            else:
                st.write("No memories yet.")

    with main_content:
        story_container = st.container(height=400, border=True)
        story_container.markdown(st.session_state.story_history)

        if st.session_state.game_over:
            st.success("The End. Thanks for playing!")
        else:
            st.subheader("What do you do next?")
            
            with st.form("choice_form"):
                selected_choice = st.radio(
                    "Choose your path:",
                    options=st.session_state.choices,
                    label_visibility="collapsed"
                )
                
                submitted = st.form_submit_button("Continue Story")

                if submitted:
                    with st.spinner("The story continues..."):
                        story_response = generate_story_turn(st.session_state.story_history, selected_choice, st.session_state.memory_list)
                        new_narrative, new_choices = parse_story_and_choices(story_response)

                        new_memories = generate_memory_updates(new_narrative)
                        st.session_state.narration_file = generate_audio(new_narrative)
                        st.session_state.image_file = generate_image(new_narrative)
                        
                        st.session_state.story_history += f"\n\n> *{selected_choice}*\n\n{new_narrative}"
                        st.session_state.memory_list.extend(new_memories)
                        st.session_state.choices = new_choices
                        
                        if any("conclusion" in choice.lower() for choice in new_choices):
                             st.session_state.game_over = True

                        st.rerun()

            if st.button("End Story Manually", type="secondary"):
                st.session_state.game_over = True
                st.session_state.story_history += "\n\n**The End.**"
                st.session_state.narration_file = generate_audio("The End.")
                st.rerun()
