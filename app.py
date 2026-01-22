import os
import random
import numpy as np
import streamlit as st

from PIL import Image, ImageDraw, ImageFont
from gtts import gTTS

from moviepy.editor import (
    ImageClip,
    AudioFileClip,
    concatenate_videoclips,
    concatenate_audioclips,
)


# ---------- PIL: TEXT -> IMAGE ----------
def make_text_frame(text, w=1080, h=1920, font_size=95, margin=80, line_gap=20):
    img = Image.new("RGB", (w, h), (0, 0, 0))
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("DejaVuSans.ttf", font_size)
    except:
        font = ImageFont.load_default()

    max_width = w - 2 * margin

    def text_width(s):
        bbox = draw.textbbox((0, 0), s, font=font)
        return bbox[2] - bbox[0]

    words = text.split()
    lines = []
    current = ""

    for word in words:
        test = (current + " " + word).strip()
        if text_width(test) <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word

    if current:
        lines.append(current)

    # center vertically
    line_heights = []
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        line_heights.append(bbox[3] - bbox[1])

    total_text_h = sum(line_heights) + (len(lines) - 1) * line_gap
    y = (h - total_text_h) // 2

    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        line_w = bbox[2] - bbox[0]
        line_h = bbox[3] - bbox[1]

        x = (w - line_w) // 2
        draw.text((x, y), line, font=font, fill=(255, 255, 255))
        y += line_h + line_gap

    return np.array(img)


# ---------- PIL: SAFE ZOOM ----------
def zoom_frame_pil(frame_np, zoom_factor, w, h):
    if zoom_factor <= 1.0:
        return frame_np

    img = Image.fromarray(frame_np)
    new_w = int(w * zoom_factor)
    new_h = int(h * zoom_factor)

    img = img.resize((new_w, new_h), resample=Image.Resampling.LANCZOS)

    left = (new_w - w) // 2
    top = (new_h - h) // 2
    img = img.crop((left, top, left + w, top + h))

    return np.array(img)


# ---------- gTTS per line ----------
def make_line_audio(text, filename, lang="en"):
    tts = gTTS(text=text, lang=lang)
    tts.save(filename)
    return filename


# ---------- BUILD PERFECTLY SYNCED VIDEO ----------
def build_synced_video(lines, w, h, font_size, fps, lang="en"):
    video_clips = []
    audio_clips = []

    os.makedirs("tts", exist_ok=True)

    for i, line in enumerate(lines):
        # 1) Generate line audio
        audio_path = f"tts/line_{i}.mp3"
        make_line_audio(line, audio_path, lang=lang)

        audio = AudioFileClip(audio_path)

        # 2) Make the frame
        frame = make_text_frame(line, w=w, h=h, font_size=font_size)
        zoom = random.uniform(1.00, 1.06)
        frame = zoom_frame_pil(frame, zoom, w, h)

        # 3) Clip duration matches the audio duration (perfect sync)
        clip = ImageClip(frame).set_duration(audio.duration).set_audio(audio)

        video_clips.append(clip)
        audio_clips.append(audio)

    final = concatenate_videoclips(video_clips, method="compose")
    final_audio = concatenate_audioclips(audio_clips)

    final = final.set_audio(final_audio)
    return final


# ---------- STREAMLIT UI ----------
st.set_page_config(page_title="Synced Text Video + Voice", layout="centered")
st.title("Text Video + Voiceover (Perfect Sync)")

default_script = """This AI tool is insane.
One prompt.
Done.
Try it today."""

script = st.text_area("Script (ONE line per cut)", value=default_script, height=220)
font_size = st.slider("Font size", 50, 140, 95, 5)

format_choice = st.selectbox(
    "Video Format",
    ["Vertical (1080x1920)", "Square (1080x1080)", "Horizontal (1920x1080)"],
)

fps = st.selectbox("FPS", [24, 30, 60], index=1)

lang = st.selectbox("Voice language", ["en"], index=0)

if format_choice == "Vertical (1080x1920)":
    w, h = 1080, 1920
elif format_choice == "Square (1080x1080)":
    w, h = 1080, 1080
else:
    w, h = 1920, 1080

if st.button("Generate MP4"):
    lines = [l.strip() for l in script.split("\n") if l.strip()]
    if not lines:
        st.error("Enter at least 1 line.")
        st.stop()

    out_path = "synced_video.mp4"

    with st.spinner("Generating TTS + rendering video..."):
        final = build_synced_video(lines, w, h, font_size, fps, lang=lang)
        final.write_videofile(
            out_path,
            fps=fps,
            codec="libx264",
            audio_codec="aac",
            verbose=False,
            logger=None,
        )

    with open(out_path, "rb") as f:
        st.download_button(
            "Download MP4",
            data=f,
            file_name="synced_text_voice.mp4",
            mime="video/mp4",
        )
