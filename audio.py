import whisper

import bot #pip install -U openai-whisper
import question

@bot.message_handler(content_types=['voice'])
def transcribe_voice_message(message):
    file_id = message.voice.file_id
    # Get url to audio file.
    file_path = bot.get_file_url(file_id)

    # Transcribe the audio using Whisper AI
    text = whisper_transcribe(file_path)

    result = generate(text)
    bot.reply_to(message, json.dumps(result))

def whisper_transcribe(filepath: str, model="tiny") -> str:
    """
    Function to perform ASR on a .mp3 file
    :param filepath: Path to the .mp3 audiofile.
    :param model: Set the model type for whisper
    ["tiny", "base", "small", "medium", "large"].
    Larger model means more parameters, higher memory requirements and
    slower speed.
    :return: transcribed audio.
    """
    # Choose tiny model for faster output.
    model = whisper.load_model(model)
    result = model.transcribe(filepath)

    return result["text"]

bot.polling()