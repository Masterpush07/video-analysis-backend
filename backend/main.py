from fastapi import FastAPI
from pydantic import BaseModel
import os, json, tempfile, shutil, yt_dlp
from google import genai
import uvicorn

app = FastAPI()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

class VideoRequest(BaseModel):
    video_url: str

@app.post("/analyze")
def analyze_video(req: VideoRequest):
    temp_dir = tempfile.mkdtemp()
    audio_path = os.path.join(temp_dir, "audio.mp3")

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": audio_path,
        "postprocessors": [
            {"key": "FFmpegExtractAudio", "preferredcodec": "mp3"}
        ]
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([req.video_url])
    except Exception as e:
        shutil.rmtree(temp_dir)
        return {"error": f"Audio extraction failed: {str(e)}"}

    try:
        uploaded = client.files.upload(file=audio_path)
    except Exception as e:
        shutil.rmtree(temp_dir)
        return {"error": f"Gemini upload failed: {str(e)}"}

    prompt = """
Return STRICT JSON only:

{
  "transcript": "string",
  "summary": "string",
  "sentiment": "string",
  "key_points": ["string"],
  "suggestions": ["string"],
  "overall_score": 0-100
}
"""

    gemini_input = [
        {
            "role": "user",
            "parts": [
                {"text": prompt},
                {
                    "file_data": {
                        "file_uri": uploaded.uri,
                        "mime_type": uploaded.mime_type
                    }
                }
            ]
        }
    ]

    try:
        resp = client.models.generate_content(
            model="gemini-2.0-flash",
            input=gemini_input
        )
        text = resp.text
        result = json.loads(text)
    except Exception as e:
        shutil.rmtree(temp_dir)
        return {"error": f"Gemini analysis failed: {str(e)}"}

    shutil.rmtree(temp_dir)
    return result


if _name_ == "_main_":
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
