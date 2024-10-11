import os
import subprocess
import sys
import re
import time
import json
from concurrent.futures import ThreadPoolExecutor
from tkinter import Tk, filedialog
from colorama import init, Fore, Style

init(autoreset=True)

AUDIO_BITRATE = "320k"
AUDIO_FILTER = "lowpass=c=LFE:f=120,pan=stereo|FL=0.3*FL+0.21*FC+0.3*FLC+0.21*SL+0.21*BL+0.15*BC+0.21*LFE|FR=0.3*FR+0.21*FC+0.3*FRC+0.21*SR+0.21*BR+0.15*BC+0.21*LFE,dynaudnorm=f=150:m=30:g=5:s=7"

ffprobe_cache = {}

def set_console_size(width, height):
    os.system(f'mode con: cols={width} lines={height}' if os.name == 'nt' else f'\x1b[8;{height};{width}t')

def get_audio_tracks(input_file):
    if input_file not in ffprobe_cache:
        command = ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_streams', '-select_streams', 'a', input_file]
        result = subprocess.run(command, capture_output=True, text=True)
        ffprobe_cache[input_file] = json.loads(result.stdout)['streams']
    return ffprobe_cache[input_file]

def select_audio_track(input_file):
    audio_tracks = get_audio_tracks(input_file)
    if len(audio_tracks) == 1:
        return "0:a:0"

    print(f"\nMultiple audio tracks available for {os.path.basename(input_file)}:")
    for i, track in enumerate(audio_tracks):
        print(f"  {i}: {track.get('tags', {}).get('language', 'Unknown')} - {track.get('codec_name', 'Unknown codec')}")

    while True:
        try:
            selection = int(input("\nPlease select audio track number: "))
            if 0 <= selection < len(audio_tracks):
                return f"0:a:{selection}"
            print("Invalid selection. Please try again.")
        except ValueError:
            print("Invalid input. Please enter a number.")

def run_command(command, step_name, progress_callback):
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        duration_regex = re.compile(r"Duration: (\d{2}):(\d{2}):(\d{2}\.\d{2})")
        time_regex = re.compile(r"time=(\d{2}):(\d{2}):(\d{2}\.\d{2})")
        duration = None

        for line in process.stderr:
            if not duration:
                match = duration_regex.search(line)
                if match:
                    duration = sum(float(x) * [3600, 60, 1][i] for i, x in enumerate(match.groups()))

            match = time_regex.search(line)
            if match and duration:
                current_time = sum(float(x) * [3600, 60, 1][i] for i, x in enumerate(match.groups()))
                progress_callback(current_time / duration)

        process.wait()
        if process.returncode != 0:
            print(f"Error during {step_name}. Return code: {process.returncode}")
            return False
        progress_callback(1.0)
        return True
    except Exception as e:
        print(f"Error during {step_name}: {e}")
        return False

def get_unique_filename(output_file):
    base, ext = os.path.splitext(output_file)
    counter = 1
    while os.path.exists(output_file):
        output_file = f"{base}({counter}){ext}"
        counter += 1
    return output_file

def process_movie(input_file, audio_map, output_dir, progress_callback):
    base, ext = os.path.splitext(os.path.basename(input_file))
    output_file = os.path.join(output_dir, f"{base}_compressed_audio{ext}")
    output_file = get_unique_filename(output_file)
    command = [
        'ffmpeg', '-i', input_file,
        '-map', '0:v:0', '-c:v', 'copy',
        '-map', audio_map,
        '-c:a', 'aac', '-b:a', AUDIO_BITRATE,
        '-af', AUDIO_FILTER,
        '-map', '0:s?', '-c:s', 'copy',
        '-y', output_file
    ]
    return run_command(command, os.path.basename(input_file), progress_callback)

def display_progress(progress_dict, start_time):
    os.system('cls' if os.name == 'nt' else 'clear')
    max_filename_length = 60

    for filename, progress in progress_dict.items():
        bar_length = 35
        filled_length = int(bar_length * progress)
        bar = '█' * filled_length + '-' * (bar_length - filled_length)
        color = Fore.GREEN if progress == 1 else Fore.YELLOW
        displayed_filename = '...' + filename[-(max_filename_length-3):] if len(filename) > max_filename_length else filename
        print(f" - {displayed_filename.ljust(max_filename_length)} [{color}{bar}{Style.RESET_ALL}] {color}{progress*100:>6.2f}%{Style.RESET_ALL}\n")

    elapsed_time = time.time() - start_time
    total_progress = sum(progress_dict.values()) / len(progress_dict)

    if total_progress > 0:
        remaining_time = (elapsed_time / total_progress) - elapsed_time
        hours, remainder = divmod(int(remaining_time), 3600)
        minutes, seconds = divmod(remainder, 60)
        print(f"\nTime remaining: {hours:02}:{minutes:02}:{seconds:02}")

def select_output_directory():
    root = Tk()
    root.withdraw()
    directory = filedialog.askdirectory(title="Select Output Directory")
    root.destroy()
    return directory

def main():
    set_console_size(115, 35)

    if len(sys.argv) < 2:
        print("Usage: Drag and drop one or more files directly on the script.")
        return

    input_files = sys.argv[1:]
    print(f"Found {len(input_files)} file(s) to process.")

    with ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
        audio_selections = dict(zip(input_files, executor.map(select_audio_track, input_files)))

    output_dir = select_output_directory()
    if not output_dir:
        print("No output directory selected. Exiting.")
        return

    print("\nStarting processing...")

    progress_dict = {os.path.basename(f): 0 for f in input_files}
    start_time = time.time()

    def update_progress(filename, progress):
        progress_dict[filename] = progress
        display_progress(progress_dict, start_time)

    with ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
        results = list(executor.map(
            process_movie,
            input_files,
            [audio_selections[f] for f in input_files],
            [output_dir]*len(input_files),
            [lambda p, f=f: update_progress(os.path.basename(f), p) for f in input_files]
        ))

    if all(results):
        print("\nAll files processed successfully.")
    else:
        failed_files = [f for f, r in zip(input_files, results) if not r]
        print(f"\n{len(failed_files)} file(s) failed to process:")
        for file in failed_files:
            print(f"  - {file}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    finally:
        input("\nPress Enter to exit...")
