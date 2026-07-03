import wave
import struct

def make_wav(filename: str, seconds: int):
    with wave.open(filename, "w") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(16000)
        f.writeframes(struct.pack("<h", 0) * 16000 * seconds)

make_wav("test_short.wav", 5)   # 5 seconds — should PASS validation
make_wav("test_long.wav", 65)   # 65 seconds — should FAIL validation

print("Test files created.")