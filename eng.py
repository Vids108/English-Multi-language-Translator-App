"""
Restored original-style Tkinter UI + stable translation + safe TTS playback.

Requirements:
pip install ttkbootstrap gTTS pygame pyttsx3 deep-translator requests pydub
and install ffmpeg if you want MP3->WAV conversion (recommended).
"""

import os
import tempfile
import threading
import time
import traceback
import random
import tkinter as tk
from tkinter import scrolledtext, messagebox, filedialog

import ttkbootstrap as ttk
from ttkbootstrap.constants import *

# TTS and playback libraries
try:
    import pyttsx3
except Exception:
    pyttsx3 = None

try:
    from gtts import gTTS
except Exception:
    gTTS = None

# pydub optional for mp3->wav conversion
try:
    from pydub import AudioSegment
except Exception:
    AudioSegment = None

# pygame for playback
try:
    import pygame
    PYGAME_AVAILABLE = True
except Exception:
    pygame = None
    PYGAME_AVAILABLE = False

import requests
from deep_translator import GoogleTranslator


# ----------------- Helper: ensure pygame mixer -----------------
def ensure_pygame():
    global PYGAME_AVAILABLE
    if not PYGAME_AVAILABLE or pygame is None:
        raise RuntimeError('pygame is required for audio playback. Install pygame in this environment.')
    try:
        if not pygame.mixer.get_init():
            pygame.mixer.init()
    except Exception as e:
        raise RuntimeError('Failed to initialize audio device: ' + str(e))


# ----------------- TTS Player -----------------
class TTSPlayer:
    """
    - Uses gTTS (preferred) to generate MP3.
    - Converts to WAV via pydub if available (recommended for pygame).
    - Uses unique temp filenames to avoid permission issues on Windows.
    """
    def __init__(self):
        self.audio_file = None     # final playable file (wav preferred)
        self._raw_mp3 = None       # raw mp3 path (if created)
        self.is_playing = False
        self.paused = False
        self.lock = threading.Lock()

    def generate(self, text, lang='en'):
        """
        Generate audio for `text` in language `lang`.
        Returns path to final audio file.
        """
        # cleanup previous files safely
        self._stop_and_cleanup_playback()
        self.cleanup()

        # Try offline pyttsx3 for en only (optional)
        if lang.startswith('en') and pyttsx3 is not None and gTTS is None:
            try:
                fd, path = tempfile.mkstemp(suffix='.wav')
                os.close(fd)
                engine = pyttsx3.init()
                engine.save_to_file(text, path)
                engine.runAndWait()
                self.audio_file = path
                return path
            except Exception as e:
                print('pyttsx3 fail, falling back to gTTS:', e)

        if gTTS is None:
            raise RuntimeError('gTTS not available. Install gTTS (pip install gTTS).')

        # create unique mp3 file
        try:
            fd_mp3, mp3_path = tempfile.mkstemp(prefix='tts_', suffix='.mp3')
            os.close(fd_mp3)
            tts = gTTS(text=text, lang=lang)
            tts.save(mp3_path)
            self._raw_mp3 = mp3_path
        except Exception as e:
            # cleanup if created
            try:
                if 'mp3_path' in locals() and os.path.exists(mp3_path):
                    os.remove(mp3_path)
            except Exception:
                pass
            raise RuntimeError('gTTS generation failed: ' + str(e))

        # Convert to WAV if pydub available (recommended)
        if AudioSegment is not None:
            try:
                fd_wav, wav_path = tempfile.mkstemp(prefix='tts_', suffix='.wav')
                os.close(fd_wav)
                audio = AudioSegment.from_file(self._raw_mp3, format='mp3')
                audio.export(wav_path, format='wav')
                # set final file and remove mp3
                self.audio_file = wav_path
                try:
                    os.remove(self._raw_mp3)
                except Exception:
                    pass
                self._raw_mp3 = None
                return self.audio_file
            except Exception as e:
                # conversion failed - fall back to mp3 playback
                print('pydub conversion failed, will try mp3 playback:', e)

        # otherwise keep mp3
        self.audio_file = self._raw_mp3
        return self.audio_file

    def play(self):
        ensure_pygame()
        if not self.audio_file or not os.path.exists(self.audio_file):
            raise RuntimeError("No audio file to play. Generate it first.")
        with self.lock:
            try:
                # if something is playing, stop first to ensure load succeeds
                try:
                    pygame.mixer.music.stop()
                except Exception:
                    pass
                pygame.mixer.music.load(self.audio_file)
                pygame.mixer.music.play()
                self.is_playing = True
                self.paused = False
            except Exception as e:
                raise RuntimeError('Playback failed: ' + str(e))

    def pause(self):
        try:
            ensure_pygame()
            if pygame.mixer.music.get_busy() and not self.paused:
                pygame.mixer.music.pause()
                self.paused = True
                self.is_playing = False
        except Exception as e:
            print('Pause error:', e)

    def resume(self):
        try:
            ensure_pygame()
            if self.paused:
                pygame.mixer.music.unpause()
                self.paused = False
                self.is_playing = True
        except Exception as e:
            print('Resume error:', e)

    def stop(self):
        try:
            ensure_pygame()
            pygame.mixer.music.stop()
            self.is_playing = False
            self.paused = False
        except Exception as e:
            print('Stop error:', e)

    def replay(self):
        with self.lock:
            try:
                ensure_pygame()
                try:
                    pygame.mixer.music.stop()
                except Exception:
                    pass
                pygame.mixer.music.load(self.audio_file)
                pygame.mixer.music.play()
                self.is_playing = True
                self.paused = False
            except Exception as e:
                print('Replay error:', e)
                raise

    def _stop_and_cleanup_playback(self):
        # Attempt to stop playback and quit mixer to release file locks
        try:
            if PYGAME_AVAILABLE and pygame is not None and pygame.mixer.get_init():
                try:
                    pygame.mixer.music.stop()
                    pygame.mixer.quit()
                except Exception:
                    pass
        except Exception:
            pass

    def cleanup(self):
        # remove temp files
        paths = []
        if self.audio_file:
            paths.append(self.audio_file)
        if self._raw_mp3:
            paths.append(self._raw_mp3)
        for p in paths:
            try:
                if p and os.path.exists(p):
                    os.remove(p)
            except Exception:
                pass
        self.audio_file = None
        self._raw_mp3 = None
        self.is_playing = False
        self.paused = False


# ------------------------- GUI App (original layout restored) -------------------------
class EnglishLearningApp(ttk.Window):
    def __init__(self):
        super().__init__(themename="superhero")
        self.title('English Multi-language Translator App')
        self.geometry('900x650')

        header = ttk.Label(self, text="✨ English Multi-language Translator App ✨",
                          font=('Poppins', 20, 'bold'), anchor='center', bootstyle=INFO)
        header.pack(fill='x', pady=8)

        # ONE global language dropdown at top (shared across tabs)
        top_controls = ttk.Frame(self)
        top_controls.pack(fill='x', padx=8, pady=4)

        ttk.Label(top_controls, text='Select language for TTS / Translation:').pack(side='left')

        # languages mapping (kept comprehensive)
        self.languages = {
            'English (en)': 'en',
            'Hindi (hi)': 'hi',
            'Bengali (bn)': 'bn',
            'Tamil (ta)': 'ta',
            'Telugu (te)': 'te',
            'Kannada (kn)': 'kn',
            'Malayalam (ml)': 'ml',
            'Marathi (mr)': 'mr',
            'Gujarati (gu)': 'gu',
            'Punjabi (pa)': 'pa',
            'Odia (or)': 'or',
            'Urdu (ur)': 'ur',
            'Nepali (ne)': 'ne',
            'Spanish (es)': 'es',
            'French (fr)': 'fr',
            'German (de)': 'de',
            'Portuguese (pt)': 'pt',
            'Japanese (ja)': 'ja',
            'Korean (ko)': 'ko',
            'Russian (ru)': 'ru',
            'Italian (it)': 'it'
        }

        self.lang_var = tk.StringVar(value='English (en)')
        self.lang_menu = ttk.OptionMenu(top_controls, self.lang_var, 'English (en)', *self.languages.keys())
        self.lang_menu.pack(side='left', padx=6)

        # Main notebook and tabs (original-like positions)
        main = ttk.Notebook(self)
        main.pack(fill='both', expand=True, padx=10, pady=8)

        # Tab 1: Practice & Audio
        tab1 = ttk.Frame(main)
        main.add(tab1, text='Practice & Audio')

        left = ttk.Frame(tab1)
        left.pack(side='left', fill='both', expand=True, padx=8, pady=8)

        right = ttk.Frame(tab1)
        right.pack(side='right', fill='y', padx=8, pady=8)

        # Context input
        ttk.Label(left, text='Enter or paste English context (leave blank for random):').pack(anchor='w')
        self.context_text = scrolledtext.ScrolledText(left, height=12, wrap='word')
        self.context_text.pack(fill='both', expand=False)

        # Buttons and language selection already at top; here only action buttons
        controls = ttk.Frame(left)
        controls.pack(fill='x', pady=6)

        gen_btn = ttk.Button(controls, text='🎧 Generate & Play Audio', bootstyle=SUCCESS, command=self.on_generate_audio)
        gen_btn.pack(side='left', padx=6)

        # Playback controls (Play / Pause / Replay)
        pb = ttk.Frame(left)
        pb.pack(fill='x', pady=4)
        self.play_btn = ttk.Button(pb, text='Play', command=self.on_play, state='disabled')
        self.play_btn.pack(side='left', padx=4)
        self.pause_btn = ttk.Button(pb, text='Pause', command=self.on_pause, state='disabled')
        self.pause_btn.pack(side='left', padx=4)
        self.replay_btn = ttk.Button(pb, text='Replay', command=self.on_replay, state='disabled')
        self.replay_btn.pack(side='left', padx=4)

        # Right pane: quick samples
        ttk.Label(right, text='Quick samples (click to use):').pack(anchor='w')
        self.sample_contexts = [
            "Introduce yourself and talk about your hobbies.",
            "Describe your favorite book and why you like it.",
            "Explain how to prepare your favorite vegetarian dish.",
            "Talk about a memorable trip you took.",
            "Describe a daily routine for a student preparing for exams.",
        ]
        for s in self.sample_contexts:
            btn = ttk.Button(right, text=(s if len(s) < 35 else s[:32] + '...'), command=lambda t=s: self.use_sample(t))
            btn.pack(fill='x', pady=3)

        ttk.Separator(self).pack(fill='x')

        # Tab 2: Word lookup
        tab2 = ttk.Frame(main)
        main.add(tab2, text='Search Word Meaning')

        search_row = ttk.Frame(tab2)
        search_row.pack(fill='x', pady=8, padx=8)
        ttk.Label(search_row, text='Word:').pack(side='left')
        self.word_var = tk.StringVar()
        ttk.Entry(search_row, textvariable=self.word_var).pack(side='left', padx=6)
        ttk.Label(search_row, text='Translate to:').pack(side='left', padx=6)
        # Reuse the global dropdown selection (no separate menu here) — show read-only display
        self.search_lang_display = ttk.Label(search_row, textvariable=self.lang_var)
        self.search_lang_display.pack(side='left', padx=6)
        ttk.Button(search_row, text='Search', command=self.on_search_word).pack(side='left', padx=6)

        self.meaning_box = scrolledtext.ScrolledText(tab2, height=12, wrap='word')
        self.meaning_box.pack(fill='both', expand=True, padx=8, pady=6)

        # Tab 3: Notes
        tab3 = ttk.Frame(main)
        main.add(tab3, text='Notes')
        ttk.Label(tab3, text='Write sentences, save and load your notes:').pack(anchor='w', padx=8, pady=6)
        self.notes_area = scrolledtext.ScrolledText(tab3, height=18)
        self.notes_area.pack(fill='both', expand=True, padx=8, pady=6)
        notes_btns = ttk.Frame(tab3)
        notes_btns.pack(fill='x', padx=8, pady=6)
        ttk.Button(notes_btns, text='Translate Notes', command=self.translate_notes).pack(side='left', padx=6)
        ttk.Button(notes_btns, text='Save Notes', command=self.save_notes).pack(side='left', padx=6)
        ttk.Button(notes_btns, text='Clear Notes', command=lambda: self.notes_area.delete('1.0', 'end')).pack(side='left', padx=6)

        # TTS player instance
        self.player = TTSPlayer()

        # Status label
        self.status_lbl = ttk.Label(self, text='')
        self.status_lbl.pack(side='bottom', fill='x')

        # Ensure app closes cleanly
        self.protocol('WM_DELETE_WINDOW', self.on_close)

    # ----------------- Event handlers & helpers -----------------
    def use_sample(self, text):
        self.context_text.delete('1.0', 'end')
        self.context_text.insert('1.0', text)

    def on_generate_audio(self):
        text = self.context_text.get('1.0', 'end').strip()
        if not text:
            text = random.choice(self.sample_contexts)
            self.context_text.insert('1.0', text)

        # disable playback buttons while generating
        self._set_playback_buttons_state('disabled')
        threading.Thread(target=self._generate_and_play_thread, args=(text,), daemon=True).start()

    def _generate_and_play_thread(self, text):
        try:
            lang_key = self.lang_var.get()
            lang_code = self.languages.get(lang_key, 'en')
            self._set_status('Translating...')
            # translate text using deep-translator
            try:
                translated = GoogleTranslator(source='auto', target=lang_code).translate(text)
            except Exception as e:
                raise RuntimeError('Translation failed: ' + str(e))

            self._set_status('Generating audio...')
            # generate TTS (this will create a unique temporary file)
            audio_path = self.player.generate(translated, lang=lang_code)

            self._set_status('Playing...')
            # initialize pygame and play (do minimal pygame init on main thread)
            try:
                ensure_pygame()
            except Exception as e:
                # show error on main thread and abort
                self.after(0, lambda: messagebox.showerror('Audio Error', str(e)))
                self.after(0, lambda: self._set_playback_buttons_state('disabled'))
                return

            # start playback on main thread
            self.after(0, lambda: self._start_playback_ui())

            # wait while playback busy
            while True:
                try:
                    busy = pygame.mixer.music.get_busy() if (PYGAME_AVAILABLE and pygame is not None) else False
                except Exception:
                    busy = False
                if not busy:
                    break
                time.sleep(0.2)

            self._set_status('Ready')
        except Exception as e:
            print('TTS error:', e)
            traceback.print_exc()
            self.after(0, lambda: messagebox.showerror('TTS Error', str(e)))
            self._set_playback_buttons_state('disabled')
            self._set_status('Error')

    def _start_playback_ui(self):
        try:
            self.player.play()
            self._enable_playback_buttons()
            self._set_status('Playing')
        except Exception as e:
            messagebox.showerror('Playback Error', str(e))
            self._set_playback_buttons_state('disabled')

    def on_play(self):
        try:
            ensure_pygame()
            if self.player.paused:
                self.player.resume()
                self._set_status('Playing')
            elif not (pygame.mixer.music.get_busy()):
                self.player.play()
                self._set_status('Playing')
        except Exception as e:
            messagebox.showerror('Play Error', str(e))

    def on_pause(self):
        try:
            if self.player.paused:
                self.player.resume()
                self.pause_btn.config(text='Pause')
                self._set_status('Playing')
            else:
                if PYGAME_AVAILABLE and pygame is not None and pygame.mixer.music.get_busy():
                    self.player.pause()
                    self.pause_btn.config(text='Resume')
                    self._set_status('Paused')
        except Exception as e:
            messagebox.showerror('Pause Error', str(e))

    def on_replay(self):
        try:
            self.player.replay()
            self._enable_playback_buttons()
            self.pause_btn.config(text='Pause')
            self._set_status('Playing')
        except Exception as e:
            messagebox.showerror('Replay Error', str(e))

    def _set_status(self, text):
        self.after(0, lambda: self.status_lbl.config(text=text))

    def _enable_playback_buttons(self):
        self._set_playback_buttons_state('normal')
        self.pause_btn.config(text='Pause')

    def _set_playback_buttons_state(self, state):
        for b in (self.play_btn, self.pause_btn, self.replay_btn):
            try:
                b.config(state=state)
            except Exception:
                pass

    # ----------------- Word lookup -----------------
    def on_search_word(self):
        word = self.word_var.get().strip()
        if not word:
            messagebox.showinfo('Input required', 'Please type a word to search for meaning.')
            return
        threading.Thread(target=self._fetch_meaning_thread, args=(word,), daemon=True).start()

    def _fetch_meaning_thread(self, word):
        try:
            self.meaning_box.delete('1.0', 'end')
            self.meaning_box.insert('1.0', f'Searching meaning for "{word}"...\n')
            url = f'https://api.dictionaryapi.dev/api/v2/entries/en/{word}'
            resp = requests.get(url, timeout=8)
            if resp.status_code != 200:
                self.meaning_box.insert('end', f'No definition found for "{word}".\n')
                return
            data = resp.json()
            short_text = ''
            if isinstance(data, list) and len(data) > 0:
                entry = data[0]
                word_title = entry.get('word', word)
                short_text += f'Word: {word_title}\n'
                phonetics = entry.get('phonetics', [])
                if phonetics:
                    p = phonetics[0].get('text')
                    if p:
                        short_text += f'Pronunciation: {p}\n'
                meanings = entry.get('meanings', [])
                if meanings:
                    first_meaning = meanings[0]
                    part = first_meaning.get('partOfSpeech', '')
                    defs = first_meaning.get('definitions', [])
                    if defs:
                        d0 = defs[0]
                        definition = d0.get('definition', '')
                        example = d0.get('example')
                        short_text += f'Part of speech: {part}\n'
                        short_text += f'Definition: {definition}\n'
                        if example:
                            short_text += f'Example: {example}\n'
                else:
                    short_text += 'No meanings found.\n'
            else:
                short_text = f'No definition found for "{word}".\n'

            # Translate short_text if requested using global language
            target_key = self.lang_var.get()
            target_code = self.languages.get(target_key, 'en')
            if target_code != 'en':
                try:
                    translated = GoogleTranslator(source='auto', target=target_code).translate(short_text)
                    full_text = '--- Original (English) ---\n' + short_text + '\n\n--- Translated ---\n' + translated
                except Exception as e:
                    full_text = short_text + f'\n\n(Translation failed: {e})'
            else:
                full_text = short_text

            self.meaning_box.delete('1.0', 'end')
            self.meaning_box.insert('1.0', full_text)
        except Exception as e:
            print('Meaning lookup error:', e)
            traceback.print_exc()
            self.meaning_box.insert('end', f'Error: {e}')

    # ----------------- Notes -----------------
    def save_notes(self):
        text = self.notes_area.get('1.0', 'end').strip()
        if not text:
            messagebox.showinfo('No Notes', 'There is nothing to save.')
            return

        file_path = filedialog.asksaveasfilename(
            title="Save Notes As",
            defaultextension=".txt",
            filetypes=[("Text Files", ".txt"), ("All Files", ".*")]
        )
        if not file_path:
            return
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(text)
            messagebox.showinfo('Saved', f'Notes successfully saved to:\n{file_path}')
        except Exception as e:
            messagebox.showerror('Save Error', str(e))

    def load_notes(self):
        file_path = filedialog.askopenfilename(
            title="Open Notes File",
            filetypes=[("Text Files", ".txt"), ("All Files", ".*")]
        )
        if not file_path:
            return
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = f.read()
            self.notes_area.delete('1.0', 'end')
            self.notes_area.insert('1.0', data)
            messagebox.showinfo('Loaded', f'Notes loaded from:\n{file_path}')
        except Exception as e:
            messagebox.showerror('Load Error', str(e))

    def translate_notes(self):
        text = self.notes_area.get('1.0', 'end').strip()
        if not text:
            messagebox.showinfo('No Notes', 'There is nothing to translate.')
            return
        target_key = self.lang_var.get()
        target_code = self.languages.get(target_key, 'en')
        try:
            translated = GoogleTranslator(source='auto', target=target_code).translate(text)
            self.notes_area.delete('1.0', 'end')
            self.notes_area.insert('1.0', translated)
        except Exception as e:
            messagebox.showerror('Translation Error', str(e))

    # ----------------- Cleanup -----------------
    def on_close(self):
        try:
            self.player.cleanup()
            if PYGAME_AVAILABLE and pygame is not None:
                try:
                    pygame.mixer.quit()
                except Exception:
                    pass
        except Exception:
            pass
        self.destroy()


# Run App
if __name__ == '__main__':
    missing = []
    if gTTS is None:
        missing.append('gTTS (pip install gTTS)')
    if not PYGAME_AVAILABLE or pygame is None:
        missing.append('pygame (pip install pygame)')
    if AudioSegment is None:
        missing.append('pydub (pip install pydub) + ffmpeg (recommended for WAV conversion)')
    if missing:
        print("Some recommended libraries may be missing:\n" + "\n".join(missing) +
              "\nThe app will still try to run, but TTS/playback may be limited. "
              "Install them in the SAME environment you run this script from.")

    app = EnglishLearningApp()
    app.mainloop()


