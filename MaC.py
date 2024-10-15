import os
import subprocess
import sys
import re
import time
import json
from concurrent.futures import ThreadPoolExecutor
from tkinter import Tk, filedialog
from colorama import Fore, Style

AUDIO_BITRATE = "320k"
AUDIO_FILTER = "lowpass=c=LFE:f=120,pan=stereo|FL=0.3*FL+0.21*FC+0.3*FLC+0.21*SL+0.21*BL+0.15*BC+0.21*LFE|FR=0.3*FR+0.21*FC+0.3*FRC+0.21*SR+0.21*BR+0.15*BC+0.21*LFE,dynaudnorm=f=150:m=30:g=5:s=7"

ffprobe_cache = {}

def is_valid_file(input_file):
    try:
        streams = json.loads(subprocess.run(['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_streams', input_file], capture_output=True, text=True).stdout)['streams']
        return any(stream['codec_type'] == 'audio' for stream in streams)
    except (json.JSONDecodeError, KeyError):
        return False

def get_audio_tracks(input_file):
    if input_file not in ffprobe_cache:
        ffprobe_cache[input_file] = json.loads(subprocess.run(['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_streams', '-select_streams', 'a', input_file], capture_output=True, text=True).stdout)['streams']
    return ffprobe_cache[input_file]

def select_audio_track(input_file):
    audio_tracks = get_audio_tracks(input_file)
    if len(audio_tracks) == 1:
        return "0:a:0"

    print(f"\nMultiple audio tracks available for {os.path.basename(input_file)}:")

    track_info = []
    for i, track in enumerate(audio_tracks):
        info = [
            f"{i}: {track.get('tags', {}).get('title', f'Track {i+1}')}",
            track.get('tags', {}).get('language', 'Unknown'),
            track.get('codec_name', 'Unknown codec'),
            f"{int(track.get('bit_rate', 0)) // 1000}k" if track.get('bit_rate') else 'Unknown',
            track.get('channel_layout', 'Unknown layout')
        ]
        track_info.append(info)

    col_widths = [max(len(str(row[i])) for row in track_info) for i in range(len(track_info[0]) - 1)]

    for row in track_info:
        print("  " + " | ".join(f"{str(item):<{col_widths[i]}}" if i < len(col_widths) else str(item) for i, item in enumerate(row)))

    while True:
        try:
            selection = int(input("\nPlease select audio track number: "))
            print()  # Restored extra print
            if 0 <= selection < len(audio_tracks):
                return f"0:a:{selection}"
            print("Invalid selection. Please try again.")
        except ValueError:
            print("Invalid input. Please enter a number.")

def process_movie(input_file, audio_map, output_dir, progress_callback):
    base, ext = os.path.splitext(os.path.basename(input_file))
    output_file = os.path.join(output_dir, f"{base}_compressed_audio{ext}")
    counter = 1
    while os.path.exists(output_file):
        output_file = os.path.join(output_dir, f"{base}_compressed_audio({counter}){ext}")
        counter += 1

    command = [
        'ffmpeg', '-i', input_file,
        '-map', '0:v:0', '-c:v', 'copy',
        '-map', audio_map,
        '-c:a', 'aac', '-b:a', AUDIO_BITRATE,
        '-af', AUDIO_FILTER,
        '-map', '0:s?', '-c:s', 'copy',
        '-y', output_file
    ]

    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    duration = None
    for line in process.stderr:
        if not duration:
            match = re.compile(r"Duration: (\d{2}):(\d{2}):(\d{2}\.\d{2})").search(line)
            if match:
                duration = sum(float(x) * [3600, 60, 1][i] for i, x in enumerate(match.groups()))
        match = re.compile(r"time=(\d{2}):(\d{2}):(\d{2}\.\d{2})").search(line)
        if match and duration:
            progress_callback((sum(float(x) * [3600, 60, 1][i] for i, x in enumerate(match.groups()))) / duration)

    if process.wait() != 0:
        return False

    progress_callback(1.0)
    return True

try:
    os.system('mode con: cols=115 lines=35' if os.name == 'nt' else '\x1b[8;35;115t')

    if len(sys.argv) < 2:
        print("Usage: Drag and drop one or more files directly on the script.")
        sys.exit()

    valid_files = []
    for file in sys.argv[1:]:
        if is_valid_file(file):
            valid_files.append(file)
        else:
            print(f"  Error: {os.path.basename(file)} is not a valid file.")

    if not valid_files:
        print("\nNo valid files to process.")
        sys.exit()

    print(f"\nFound {len(valid_files)} valid file(s):")
    for file in valid_files:
        print(f" - {os.path.basename(file)}")
    print()

    audio_selections = {}
    for file in valid_files:
        audio_selections[file] = select_audio_track(file)

    print("\nPlease select output directory...\n")

    output_dir = filedialog.askdirectory(title="Select Output Directory")
    if not output_dir:
        print("\nNo output directory selected.")
        sys.exit()

    print("\nStarting process...")
    progress_dict = {os.path.basename(f): 0 for f in valid_files}
    start_time = time.time()

    def update_progress(filename, progress):
        progress_dict[filename] = progress
        os.system('cls' if os.name == 'nt' else 'clear')
        max_filename_length = 60
        for fname, prog in progress_dict.items():
            bar_length, filled_length = 35, int(35 * prog)
            bar = '█' * filled_length + '-' * (bar_length - filled_length)
            color = Fore.GREEN if prog == 1 else Fore.YELLOW
            displayed_filename = '...' + fname[-(max_filename_length-3):] if len(fname) > max_filename_length else fname
            print(f" - {displayed_filename.ljust(max_filename_length)} [{color}{bar}{Style.RESET_ALL}] {color}{prog*100:>6.2f}%{Style.RESET_ALL}\n")

        elapsed_time = time.time() - start_time
        total_progress = sum(progress_dict.values()) / len(progress_dict)
        if total_progress > 0:
            hours, remainder = divmod(int((elapsed_time / total_progress) - elapsed_time), 3600)
            minutes, seconds = divmod(remainder, 60)
            print(f"\nTime remaining: {hours:02}:{minutes:02}:{seconds:02}")

    with ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
        results = list(executor.map(
            process_movie,
            valid_files,
            [audio_selections[f] for f in valid_files],
            [output_dir]*len(valid_files),
            [lambda p, f=f: update_progress(os.path.basename(f), p) for f in valid_files]
        ))

    failed_files = [f for f, r in zip(valid_files, results) if not r]
    print(f"\n{'All files processed successfully.' if not failed_files else f'{len(failed_files)} file(s) failed to process:'}")
    for file in failed_files:
        print(f" - {file}")

except Exception as e:
    print(f"An unexpected error occurred: {e}")

finally:
    input("\nPress Enter to exit...")