import json
import os
from pathlib import Path
import time
from dotenv import load_dotenv
import google.generativeai as genai
import cv2
import os
import numpy as np
from config import EXTRACTED_IMAGES_DIR
from image_helpers import generate_collage
from moviepy import VideoFileClip


def ask_user_input():
    print("Using a video model. What would you like me to find in the video?")
    user_input = input()
    while not user_input.strip():
        print("Please type a word.")
        user_input = input()
    return user_input


def connect_to_gemini():
    """
    Connect to Gemini API using API key from .env file
    Returns configured Gemini model
    """
    try:
        load_dotenv()
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            raise ValueError("GEMINI_API_KEY not found in .env file")

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-pro')
        return model

    except ValueError as ve:
        print(f"Error: {ve}")
        raise  
    except Exception as e:
        print(f"An unexpected error occurred while connecting to Gemini: {e}")
        raise


def chat_with_gemini(user_input, video_file_path="./The Super Mario Bros. Movie ｜ Official Trailer.mp4"):
    """
    Sends a video to Gemini by extracting frames and sending them with the user input.
    """
    model = connect_to_gemini()
    print("connected to model ✅")

    # Get video duration using moviepy
    try:
        with VideoFileClip(video_file_path) as clip:
            video_duration = clip.duration  
    except Exception as e:
        raise ValueError(f"Error extracting video duration: {e}")

    video_file = genai.upload_file(video_file_path)
    print("uploaded video 📤")
    # Check processing status with a timeout
    max_retries = 10  # Adjust the maximum retries as needed
    retries = 0
    State = video_file.state.__class__

    while video_file.state != State.ACTIVE:
        print(f"Waiting for video file to become ACTIVE⏳. Current state: {video_file.state}. Retry {retries + 1}/{max_retries}")
        time.sleep(15)
        video_file = genai.get_file(video_file.name)
        retries += 1

    response = model.generate_content(
    [f"""
    You are a video search engine. Analyze the given video and identify the best scenes matching the user input in this video.
    Provide the results ONLY in the following JSON format with NO explanation at all:
    ['00:10.105', '00:20.030']
    Make sure:
    1. return only the list of frames
    2. Give unique and clear frames.
    3. Keep at least 0.5 seconds between frames.
    4. times are within the video duration ({video_duration} seconds).
    5. Try to avoid blurry images, black screens, or frames with poor visibility.
    User input: {user_input}
    """, video_file],
    generation_config=genai.GenerationConfig(
        temperature=0.1,
        max_output_tokens=400
    )
)
   # Handle the response
    if response and hasattr(response, "text"):
        response_text = response.text.strip()
        # Remove all backticks and markers (generalized cleaning)
        response_text = response_text.replace("```json", "").replace("```", "").strip()
        response_text = response_text.replace("'", '"')
        try:
            # Parse the cleaned response
            return json.loads(response_text)
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON: {e}")
            raise
        except ValueError as e:
            print(f"Validation error: {e}")
            raise
    else:
        raise ValueError("Invalid or empty response from the API.")



def extract_frames_from_video(time_points, video_path="./The Super Mario Bros. Movie ｜ Official Trailer.mp4"):
    """
    Extracts frames from the video based on given time points.

    Args:
        time_points (list): List of time points as strings (e.g., ['00:20.031', '00:25.030']).
        video_path (str): Path to the video mp4 file.

    Returns:
        str: The folder where the images are extracted and saved.
    """
    # Ensure the video file exists
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"The video file '{video_path}' was not found.")
    
    output_dir = EXTRACTED_IMAGES_DIR
    os.makedirs(output_dir, exist_ok=True)
    
    # Load the video
    video = cv2.VideoCapture(video_path)
    if not video.isOpened():
        raise ValueError(f"Could not open the video file '{video_path}'.")

    frames_per_second = video.get(cv2.CAP_PROP_FPS)
    extracted_files = []

    for time_point in time_points:
        try:
            # Parse time point into seconds
            time_in_seconds = sum(float(x) * 60 ** i for i, x in enumerate(reversed(time_point.split(':'))))
        except ValueError:
            print(f"Invalid time point: {time_point}. Skipping.")
            continue

        frame_number = int(time_in_seconds * frames_per_second)
        video.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
        success, frame = video.read()
        if success:
            # Save the frame as an image file
            output_file = os.path.join(output_dir, f"frame_{int(time_in_seconds)}s.jpg")
            cv2.imwrite(output_file, frame)
            extracted_files.append(output_file)
        else:
            print(f"Warning: Could not extract frame at {time_point}.")

    video.release()
    return output_dir



def search_by_video():
    """
        This function facilitates a search process based on video input and user request.
        Returns: a collage based on extracted video frames.
    """
    user_input = ask_user_input()
    response = chat_with_gemini(user_input)
    directory_name = extract_frames_from_video(response)
    files = os.listdir(directory_name)
    image_paths_str = [str(Path(directory_name).joinpath(file)) for file in files]
    generate_collage(image_paths_str)

if __name__ == "__main__":
    search_by_video()
