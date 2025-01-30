# Movie Audio Compressor (MaC)

A Python script to quickly compress the audio dynamic range of video files, preventing large volume fluctuations (e.g., to play a movie at night, or at low volume).

_Note: Original file format and subtitles are preserved, video track remains untouched_

## Requirements

- [Python 3.6+](https://www.python.org/downloads/)
- [FFmpeg](https://www.gyan.dev/ffmpeg/builds/) ([Add to PATH](https://phoenixnap.com/kb/ffmpeg-windows))
- [colorama](https://pypi.org/project/colorama/) `pip install colorama`

## Usage

1. Drag and drop file(s) directly onto the script (files that don't include an audio stream will be ignored)
2. Select audio track if multiple are available
3. Choose output directory

## Configuration

Modify `CONFIG` at the top of the script to adjust:

- Audio codec and bitrate <sub>_Default: AAC 320kbps_</sub>
- Audio filter settings <sub>_Default: Custom downmix to stereo (see [FFmpeg documentation](https://ffmpeg.org/ffmpeg-all.html)) and use of [dynaudnorm](http://underpop.online.fr/f/ffmpeg/help/dynaudnorm.htm.gz) for compression_</sub>
- Console window size
