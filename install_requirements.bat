@echo off
echo Installing required packages with current Python interpreter...
python -m pip install --upgrade pip
python -m pip install requests plexapi beautifulsoup4 imdbpy Pillow customtkinter CTkMessagebox
echo Installation complete.
pause
