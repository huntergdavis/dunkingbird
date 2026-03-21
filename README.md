# Dunking Bird

![Dunking Bird](dunkingbird.png)

A simple automation tool that sends text to the currently active window at regular intervals. Perfect for keeping coding agents engaged with prompts like "continue" or "keep going".

## Features

- **Simple GUI**: Easy-to-use interface with start/stop controls
- **Configurable Interval**: Set custom time intervals (in minutes)
- **Custom Text**: Send any text you want to the active window
- **Automatic Enter**: Automatically presses Enter after sending text
- **Real-time Countdown**: Shows when the next text will be sent
- **Background Operation**: Runs in the background while you work

## Installation

1. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Make the script executable** (optional):
   ```bash
   chmod +x dunking_bird.py
   ```

## Usage

1. **Run the application**:
   ```bash
   python3 dunking_bird.py
   ```

2. **Configure your settings**:
   - Set the **interval** in minutes (default: 10 minutes)
   - Enter the **text** you want to send in the text area (default: "continue")

3. **Start the automation**:
   - Click the "Start" button
   - The application will send your text to whatever window is active every interval
   - Use "Stop" to pause the automation

## Use Cases

- **Coding Agents**: Keep AI coding assistants engaged with prompts like "continue", "keep going", or "proceed"
- **Terminal Sessions**: Send commands to terminals or shells at regular intervals
- **Automated Responses**: Send regular responses to any application that accepts text input

## Important Notes

- The text is sent to whatever window is currently active (has focus)
- The application automatically presses Enter after sending the text
- Make sure the target window can accept keyboard input
- The application runs in the background - you can minimize it while it works

## Example Workflow

1. Start your coding agent or terminal
2. Launch Dunking Bird
3. Set interval to 10 minutes
4. Enter "continue working" in the text area
5. Click Start
6. Switch to your coding agent window
7. Every 10 minutes, "continue working" + Enter will be sent automatically

## Troubleshooting

- **Text not being sent**: Make sure the target window is active and can accept keyboard input
- **Permission errors**: On some Linux systems, you may need to install additional packages or configure permissions for keyboard automation
- **Application not starting**: Ensure Python 3 and tkinter are installed (`sudo apt install python3-tk` on Ubuntu/Debian)

## Requirements

- Python 3.6+
- tkinter (usually included with Python)
- pynput (install via requirements.txt)